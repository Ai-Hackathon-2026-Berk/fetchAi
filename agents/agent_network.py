"""Real agent-to-agent procurement workflow.

The local workflow keeps demos deterministic. This module is the next layer: the
orchestrator asks a Registry agent for sellers, asks farm agents for quotes, then
orders and pays the winners.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agents.llm import BuyerIntent, parse_buyer_intent, use_mock_intent_parser
from agents.optimizer import Quote, optimize_split
from agents.payments import (
    STRIPE_CONNECT_FARM_PAYMENT_MODE,
    fund_order_from_buyer,
    get_buyer_payment_mode,
    get_payment_mode,
    no_buyer_funding,
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


async def run_procurement_via_agents(
    *,
    ctx: Any,
    registry_address: str,
    buyer_text: str,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    wallet: Any | None = None,
    timeout: int = 15,
) -> ProcurementRun:
    order_id = f"order-{uuid4().hex[:8]}"
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

    buyer_funding = fund_order_from_buyer(
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

    address_by_farmer = {response.farmer: address for address, response in quote_responses}
    settlements: list[FarmSettlement] = []
    for allocation in split.allocations:
        address = address_by_farmer[allocation.seller]
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
