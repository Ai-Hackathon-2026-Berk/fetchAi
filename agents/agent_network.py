"""Real agent-to-agent procurement workflow.

The local workflow keeps demos deterministic. This module is the next layer: the
orchestrator asks a Registry agent for sellers, asks farm agents for quotes, then
orders and pays the winners.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agents.llm import BuyerIntent, parse_buyer_intent, use_mock_intent_parser
from agents.optimizer import Quote, SplitResult, optimize_split
from agents.order_store import (
    PendingOrder,
    delete_pending_order,
    latest_pending_order,
    load_pending_order,
    save_pending_order,
)
from agents.payments import (
    BuyerFundingResult,
    STRIPE_BUYER_PAYMENT_MODE,
    STRIPE_CONNECT_FARM_PAYMENT_MODE,
    fund_order_from_buyer,
    get_buyer_payment_mode,
    get_payment_mode,
    no_buyer_funding,
    retrieve_stripe_checkout_session,
    settle_farm_payment,
)
from agents.protocols import (
    Invoice,
    PaymentSent,
    PurchaseOrder,
    QuoteRequest,
    QuoteResponse,
    Receipt,
    SellerList,
    WhoSells,
)
from agents.workflow import FarmSettlement, ProcurementRun


class AgentWorkflowError(RuntimeError):
    pass


def _overlay_live_quote(
    quotes: tuple[Quote, ...],
    business_quote: Quote,
) -> tuple[tuple[Quote, ...], Quote | None]:
    """Replace a responding farmer's quote with the live Business Agent price.

    Only applies when a farmer with the same name already quoted (so the structured
    PurchaseOrder/Invoice/Payment settlement stays valid), and clamps the live quantity
    to what that farmer said it can supply. Returns the (possibly unchanged) quotes plus
    the applied quote, or None if it was not applied.
    """

    match = next((quote for quote in quotes if quote.seller == business_quote.seller), None)
    if match is None:
        return quotes, None

    qty_available = max(0, min(business_quote.qty_available, match.qty_available))
    if qty_available <= 0 or business_quote.unit_price <= 0:
        return quotes, None

    applied = Quote(
        seller=match.seller,
        item=match.item,
        qty_available=qty_available,
        unit_price=business_quote.unit_price,
    )
    updated = tuple(applied if quote.seller == match.seller else quote for quote in quotes)
    return updated, applied


async def run_procurement_via_agents(
    *,
    ctx: Any,
    registry_address: str,
    buyer_text: str,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    wallet: Any | None = None,
    timeout: int = 15,
    buyer_funding_override: BuyerFundingResult | None = None,
    business_quote: Quote | None = None,
) -> ProcurementRun:
    order_id = buyer_funding_override.order_id if buyer_funding_override else f"order-{uuid4().hex[:8]}"
    request_id = f"quote-{uuid4().hex[:8]}"
    mode = get_payment_mode(payment_mode)
    buyer_mode = get_buyer_payment_mode()
    intent = parse_buyer_intent(
        buyer_text,
        use_mock=use_mock_intent_parser(intent_mode),
    )
    transcript = [
        f"Buyer intent parsed: {intent.qty} {intent.item}"
        + (f" under {intent.budget:.2f} FET." if intent.budget is not None else ".")
    ]

    seller_msg, _status = await ctx.send_and_receive(
        registry_address,
        WhoSells(item=intent.item),
        SellerList,
        timeout=timeout,
    )
    if not isinstance(seller_msg, SellerList):
        raise AgentWorkflowError("Registry did not return a seller list")

    seller_addresses = list(seller_msg.addresses)
    transcript.append(f"Registry returned {len(seller_addresses)} seller addresses.")

    quote_responses: list[tuple[str, QuoteResponse]] = []
    for address in seller_addresses:
        transcript.append(f"Sent QuoteRequest to farm agent {address}.")
        response, _status = await ctx.send_and_receive(
            address,
            QuoteRequest(item=intent.item, qty=intent.qty, request_id=request_id),
            QuoteResponse,
            timeout=timeout,
        )
        if isinstance(response, QuoteResponse):
            quote_responses.append((address, response))
        else:
            transcript.append(f"Skipped seller {address}: quote timed out or failed.")

    quotes = tuple(
        Quote(
            seller=response.farmer,
            item=response.item,
            qty_available=response.qty_available,
            unit_price=response.unit_price,
        )
        for _address, response in quote_responses
    )
    if not quotes:
        raise AgentWorkflowError("No sellers returned usable quotes")

    if business_quote is not None:
        quotes, applied = _overlay_live_quote(quotes, business_quote)
        if applied is not None:
            transcript.append(
                f"Live Business Agent quote from {applied.seller}: "
                f"{applied.qty_available} @ {applied.unit_price:.2f}."
            )

    quote_text = ", ".join(
        f"{quote.seller}: {quote.qty_available} @ {quote.unit_price:.2f} FET"
        for quote in quotes
    )
    transcript.append(f"Quotes received: {quote_text}.")

    split = optimize_split(list(quotes), qty_needed=intent.qty, budget=intent.budget)
    plan_text = " + ".join(
        f"{allocation.qty} from {allocation.seller}" for allocation in split.allocations
    )
    transcript.append(f"Optimal split: {plan_text} = {split.total_cost:.2f} FET.")

    if split.shortfall or split.over_budget:
        reason = "order shortfall" if split.shortfall else "order exceeds buyer budget"
        buyer_funding = no_buyer_funding(
            order_id=order_id,
            reason=reason,
        )
        if split.shortfall:
            transcript.append(f"Shortfall: {split.shortfall} {intent.item}. No payment executed.")
        else:
            transcript.append(
                f"Plan exceeds budget by {split.total_cost - (intent.budget or 0):.2f} FET. "
                "No payment executed."
            )
        return ProcurementRun(
            order_id=order_id,
            intent=intent,
            quotes=quotes,
            split=split,
            buyer_funding=buyer_funding,
            settlements=(),
            transcript=tuple(transcript),
            payment_mode=mode,
            buyer_payment_mode=buyer_mode,
        )

    buyer_funding = buyer_funding_override or fund_order_from_buyer(
        order_id=order_id,
        item=intent.item,
        qty=intent.qty,
        amount=split.total_cost,
        mode=buyer_mode,
    )
    transcript.append(
        f"Buyer funding: {buyer_funding.provider} {buyer_funding.status} "
        f"({buyer_funding.receipt_ref})."
    )

    if _is_checkout_pending(buyer_funding):
        save_pending_order(
            PendingOrder(
                order_id=order_id,
                buyer_text=buyer_text,
                checkout_session_id=buyer_funding.reference,
                amount=buyer_funding.amount,
                currency=buyer_funding.currency,
            )
        )
        transcript.append("Checkout is pending. Live farm purchase orders will run after Stripe confirms payment.")
        return ProcurementRun(
            order_id=order_id,
            intent=intent,
            quotes=quotes,
            split=split,
            buyer_funding=buyer_funding,
            settlements=(),
            transcript=tuple(transcript),
            payment_mode=mode,
            buyer_payment_mode=buyer_mode,
        )

    address_by_farmer = {response.farmer: address for address, response in quote_responses}
    settlements: list[FarmSettlement] = []
    for allocation in split.allocations:
        address = address_by_farmer[allocation.seller]
        transcript.append(f"Sent PurchaseOrder to {allocation.seller} agent at {address}.")
        invoice_msg, _status = await ctx.send_and_receive(
            address,
            PurchaseOrder(
                order_id=order_id,
                item=allocation.item,
                qty=allocation.qty,
                agreed_unit_price=allocation.unit_price,
            ),
            Invoice,
            timeout=timeout,
        )
        if not isinstance(invoice_msg, Invoice):
            transcript.append(f"Skipped payment to {allocation.seller}: invoice failed.")
            continue

        recipient = invoice_msg.pay_to_address
        if mode == STRIPE_CONNECT_FARM_PAYMENT_MODE and invoice_msg.stripe_connected_account_id:
            recipient = invoice_msg.stripe_connected_account_id

        payment = await settle_farm_payment(
            order_id=order_id,
            recipient=recipient,
            amount_fet=invoice_msg.total_fet,
            mode=mode,
            ledger=getattr(ctx, "ledger", None),
            wallet=wallet,
            reason=f"agent-network payout to {allocation.seller}",
        )
        receipt_msg, _status = await ctx.send_and_receive(
            address,
            PaymentSent(
                order_id=order_id,
                tx_hash=payment.tx_hash,
                amount_fet=payment.amount_fet,
            ),
            Receipt,
            timeout=timeout,
        )
        receipt_message = (
            receipt_msg.message
            if isinstance(receipt_msg, Receipt)
            else f"{allocation.seller} payment sent; receipt timed out."
        )
        settlements.append(FarmSettlement(allocation, payment, receipt_message))
        transcript.append(
            f"Paid {allocation.seller}: {payment.amount_fet:.2f} FET "
            f"({payment.receipt_ref}); {receipt_message}"
        )

    transcript.append(
        f"Done: {intent.qty} {intent.item} sourced for {split.total_cost:.2f} FET "
        "through live agent messages."
    )
    return ProcurementRun(
        order_id=order_id,
        intent=intent,
        quotes=quotes,
        split=split,
        buyer_funding=buyer_funding,
        settlements=tuple(settlements),
        transcript=tuple(transcript),
        payment_mode=mode,
        buyer_payment_mode=buyer_mode,
    )


async def confirm_pending_order_via_agents(
    *,
    ctx: Any,
    registry_address: str,
    order_id: str | None = None,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    wallet: Any | None = None,
    timeout: int = 15,
) -> ProcurementRun | None:
    pending = load_pending_order(order_id) if order_id else latest_pending_order()
    if pending is None:
        return None

    funding = retrieve_stripe_checkout_session(
        session_id=pending.checkout_session_id,
        order_id=pending.order_id,
        amount=pending.amount,
        currency=pending.currency,
    )
    if funding.status != "paid":
        intent = parse_buyer_intent(
            pending.buyer_text,
            use_mock=use_mock_intent_parser(intent_mode),
        )
        return ProcurementRun(
            order_id=pending.order_id,
            intent=intent,
            quotes=(),
            split=SplitResult(
                item=intent.item,
                requested_qty=intent.qty,
                allocated_qty=0,
                total_cost=pending.amount,
                allocations=(),
                shortfall=0,
                over_budget=False,
                budget=intent.budget,
            ),
            buyer_funding=funding,
            settlements=(),
            transcript=("Stripe Checkout is not paid yet.",),
            payment_mode=get_payment_mode(payment_mode),
            buyer_payment_mode=STRIPE_BUYER_PAYMENT_MODE,
        )

    delete_pending_order(pending.order_id)
    return await run_procurement_via_agents(
        ctx=ctx,
        registry_address=registry_address,
        buyer_text=pending.buyer_text,
        payment_mode=payment_mode,
        intent_mode=intent_mode,
        wallet=wallet,
        timeout=timeout,
        buyer_funding_override=funding,
    )


def _is_checkout_pending(funding: BuyerFundingResult) -> bool:
    return (
        funding.provider == "stripe"
        and not funding.simulated
        and funding.amount > 0
        and funding.status != "paid"
    )
