"""End-to-end procurement workflow used by the orchestrator and local demo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.farm_state import FarmState
from agents.llm import BuyerIntent, parse_buyer_intent, use_mock_intent_parser
from agents.optimizer import Allocation, Quote, SplitResult, optimize_split
from agents.order_store import (
    PendingOrder,
    delete_pending_order,
    latest_pending_order,
    load_pending_order,
    save_pending_order,
)
from agents.payments import (
    BuyerFundingResult,
    PaymentResult,
    STRIPE_BUYER_PAYMENT_MODE,
    STRIPE_CONNECT_FARM_PAYMENT_MODE,
    TESTNET_PAYMENT_MODE,
    fund_order_from_buyer,
    get_buyer_payment_mode,
    get_payment_mode,
    no_buyer_funding,
    retrieve_stripe_checkout_session,
    settle_farm_payment,
)


@dataclass(frozen=True, slots=True)
class FarmSettlement:
    allocation: Allocation
    payment: PaymentResult
    receipt_message: str


@dataclass(frozen=True, slots=True)
class ProcurementRun:
    order_id: str
    intent: BuyerIntent
    quotes: tuple[Quote, ...]
    split: SplitResult
    buyer_funding: BuyerFundingResult
    settlements: tuple[FarmSettlement, ...]
    transcript: tuple[str, ...]
    payment_mode: str
    buyer_payment_mode: str

    @property
    def status(self) -> str:
        if self.split.shortfall:
            return "partial"
        if self.split.over_budget:
            return "over_budget"
        if _is_checkout_pending(self.buyer_funding):
            return "payment_pending"
        return "confirmed"


def load_farms(config_path: Path = Path("config/farms.json")) -> list[FarmState]:
    payload = json.loads(config_path.read_text())
    return [FarmState.from_config(farm) for farm in payload["farms"]]


def run_procurement_locally(
    buyer_text: str,
    *,
    farms: list[FarmState] | None = None,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    ledger: Any | None = None,
    wallet: Any | None = None,
    business_quote: Quote | None = None,
) -> ProcurementRun:
    import asyncio

    return asyncio.run(
        run_procurement(
            buyer_text,
            farms=farms,
            payment_mode=payment_mode,
            intent_mode=intent_mode,
            ledger=ledger,
            wallet=wallet,
            business_quote=business_quote,
        )
    )


async def run_procurement(
    buyer_text: str,
    *,
    farms: list[FarmState] | None = None,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    ledger: Any | None = None,
    wallet: Any | None = None,
    buyer_funding_override: BuyerFundingResult | None = None,
    business_quote: Quote | None = None,
) -> ProcurementRun:
    order_id = buyer_funding_override.order_id if buyer_funding_override else f"order-{uuid4().hex[:8]}"
    mode = get_payment_mode(payment_mode)
    buyer_mode = get_buyer_payment_mode()
    farms = farms or load_farms()
    intent = parse_buyer_intent(
        buyer_text,
        use_mock=use_mock_intent_parser(intent_mode),
    )
    transcript = [
        f"Buyer intent parsed: {intent.qty} {intent.item}"
        + (f" under {intent.budget:.2f}." if intent.budget is not None else ".")
    ]

    sellers = [farm for farm in farms if farm.has_item(intent.item)]
    transcript.append(f"Found {len(sellers)} sellers for {intent.item}.")

    quote_list = [farm.quote(intent.item, intent.qty) for farm in sellers]
    if business_quote is not None:
        quote_list, applied = _overlay_business_quote(quote_list, business_quote, sellers, intent.item)
        if applied is not None:
            transcript.append(
                f"Live Business Agent quote from {applied.seller}: "
                f"{applied.qty_available} @ {applied.unit_price:.2f}."
            )
    quotes = tuple(quote_list)
    quote_text = ", ".join(
        f"{quote.seller}: {quote.qty_available} @ {quote.unit_price:.2f}"
        for quote in quotes
    )
    transcript.append(f"Quotes received: {quote_text}.")

    split = optimize_split(list(quotes), qty_needed=intent.qty, budget=intent.budget)
    plan_text = " + ".join(
        f"{allocation.qty} from {allocation.seller}" for allocation in split.allocations
    )
    transcript.append(f"Optimal split: {plan_text} = {split.total_cost:.2f}.")

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
                f"Plan exceeds budget by {split.total_cost - (intent.budget or 0):.2f}. "
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
        transcript.append("Checkout is pending. Farm payouts will run after Stripe confirms payment.")
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

    settlements: list[FarmSettlement] = []
    farms_by_name = {farm.name: farm for farm in farms}
    for allocation in split.allocations:
        farm = farms_by_name[allocation.seller]
        total = farm.invoice_total(allocation.item, allocation.qty, allocation.unit_price)
        recipient = farm_payment_recipient(farm, mode)
        payment = await settle_farm_payment(
            order_id=order_id,
            recipient=recipient,
            amount_fet=total,
            mode=mode,
            ledger=ledger,
            wallet=wallet,
            reason=f"local demo payout to {farm.name}",
        )
        farm.fulfill(allocation.item, allocation.qty)
        receipt_message = (
            f"{farm.name} confirmed {allocation.qty} {allocation.item}; "
            f"remaining stock {farm.catalog[allocation.item].stock}."
        )
        settlements.append(FarmSettlement(allocation, payment, receipt_message))
        transcript.append(
            f"Paid {farm.name}: {total:.2f} ({payment.receipt_ref}); "
            f"{receipt_message}"
        )

    if split.shortfall:
        transcript.append(f"Shortfall: {split.shortfall} {intent.item}.")
    elif split.over_budget:
        transcript.append(
            f"Plan exceeds budget by {split.total_cost - (intent.budget or 0):.2f}."
        )
    else:
        transcript.append(f"Done: {intent.qty} {intent.item} sourced for {split.total_cost:.2f}.")

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


async def run_business_procurement(
    buyer_text: str,
    *,
    business_quote: Quote,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    buyer_funding_override: BuyerFundingResult | None = None,
) -> ProcurementRun:
    order_id = buyer_funding_override.order_id if buyer_funding_override else f"order-{uuid4().hex[:8]}"
    mode = get_payment_mode(payment_mode)
    buyer_mode = get_buyer_payment_mode()
    intent = parse_buyer_intent(
        buyer_text,
        use_mock=use_mock_intent_parser(intent_mode),
    )
    quote = Quote(
        seller=business_quote.seller,
        item=business_quote.item,
        qty_available=business_quote.qty_available,
        unit_price=business_quote.unit_price,
    )
    transcript = [
        f"Buyer intent parsed: {intent.qty} {intent.item}"
        + (f" under {intent.budget:.2f}." if intent.budget is not None else "."),
        f"Business Agent quote from {quote.seller}: {quote.qty_available} @ {quote.unit_price:.2f}.",
    ]

    split = optimize_split([quote], qty_needed=intent.qty, budget=intent.budget)
    plan_text = " + ".join(
        f"{allocation.qty} from {allocation.seller}" for allocation in split.allocations
    )
    transcript.append(f"Business-only split: {plan_text} = {split.total_cost:.2f}.")

    if split.shortfall or split.over_budget:
        reason = "order shortfall" if split.shortfall else "order exceeds buyer budget"
        buyer_funding = no_buyer_funding(order_id=order_id, reason=reason)
        if split.shortfall:
            transcript.append(f"Shortfall: {split.shortfall} {intent.item}. No payment executed.")
        else:
            transcript.append(
                f"Plan exceeds budget by {split.total_cost - (intent.budget or 0):.2f}. "
                "No payment executed."
            )
        return ProcurementRun(
            order_id=order_id,
            intent=intent,
            quotes=(quote,),
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
                mode="business",
                seller=quote.seller,
                item=quote.item,
                qty_available=quote.qty_available,
                unit_price=quote.unit_price,
            )
        )
        transcript.append("Checkout is pending. Business Agent order confirmation will run after Stripe confirms payment.")
        return ProcurementRun(
            order_id=order_id,
            intent=intent,
            quotes=(quote,),
            split=split,
            buyer_funding=buyer_funding,
            settlements=(),
            transcript=tuple(transcript),
            payment_mode=mode,
            buyer_payment_mode=buyer_mode,
        )

    settlements = tuple(
        FarmSettlement(
            allocation=allocation,
            payment=PaymentResult(
                order_id=order_id,
                recipient=quote.seller,
                amount_fet=allocation.total_cost,
                tx_hash=f"business-confirmed-{uuid4().hex[:10]}",
                status="business_agent_confirmed",
                simulated=True,
                reason="Business Agent order confirmation",
            ),
            receipt_message=(
                f"{quote.seller} Business Agent confirmed {allocation.qty} "
                f"{allocation.item} for preparation."
            ),
        )
        for allocation in split.allocations
    )
    transcript.append(
        f"Done: {intent.qty} {intent.item} sourced from {quote.seller} Business Agent "
        f"for {split.total_cost:.2f}."
    )
    return ProcurementRun(
        order_id=order_id,
        intent=intent,
        quotes=(quote,),
        split=split,
        buyer_funding=buyer_funding,
        settlements=settlements,
        transcript=tuple(transcript),
        payment_mode=mode,
        buyer_payment_mode=buyer_mode,
    )


async def confirm_pending_order(
    order_id: str | None = None,
    *,
    farms: list[FarmState] | None = None,
    payment_mode: str | None = None,
    intent_mode: str | None = None,
    ledger: Any | None = None,
    wallet: Any | None = None,
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
        intent = parse_buyer_intent(pending.buyer_text, use_mock=use_mock_intent_parser(intent_mode))
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
    if pending.mode == "business":
        if not pending.seller or not pending.item or pending.qty_available is None or pending.unit_price is None:
            raise ValueError("Pending Business Agent order is missing quote details")
        return await run_business_procurement(
            pending.buyer_text,
            business_quote=Quote(
                seller=pending.seller,
                item=pending.item,
                qty_available=pending.qty_available,
                unit_price=pending.unit_price,
            ),
            payment_mode=payment_mode,
            intent_mode=intent_mode,
            buyer_funding_override=funding,
        )
    return await run_procurement(
        pending.buyer_text,
        farms=farms,
        payment_mode=payment_mode,
        intent_mode=intent_mode,
        ledger=ledger,
        wallet=wallet,
        buyer_funding_override=funding,
    )


def format_procurement_response(run: ProcurementRun) -> str:
    currency = _display_currency(run)
    if _is_paid_stripe_confirmation(run):
        return _format_paid_stripe_confirmation(run, currency)
    if _is_unpaid_stripe_confirmation(run):
        return _format_unpaid_stripe_confirmation(run, currency)

    quote_lines = [
        f"- {quote.seller}: {quote.qty_available} @ {_format_money(quote.unit_price, currency)}"
        for quote in run.quotes
    ]
    settlements_by_seller = {
        settlement.allocation.seller: settlement for settlement in run.settlements
    }
    allocation_lines = [
        f"- {_format_allocation_line(allocation, settlements_by_seller.get(allocation.seller), currency)}"
        for allocation in run.split.allocations
    ]
    budget = "none" if run.intent.budget is None else _format_money(run.intent.budget, currency)
    payment_label = _format_farm_payout_mode(run)
    buyer_label = _format_buyer_payment_mode(run)

    lines = [
        f"AgriBroker found {len(run.quotes)} sellers for {run.intent.item}.",
        "",
        "Quotes:",
        *quote_lines,
        "",
        "Optimal split:",
        *allocation_lines,
        "",
        "Receipt:",
        f"- Total: {_format_money(run.split.total_cost, currency)}",
        f"- Budget: {budget}",
        f"- Status: {run.status}",
        f"- Buyer payment: {buyer_label}",
        f"- Buyer funding: {_format_buyer_funding(run)}",
        f"- Farm payout mode: {payment_label}",
        *_format_stripe_step_lines(run, currency),
        *_format_agent_trace_lines(run),
        *_format_fulfillment_lines(run),
    ]

    if run.status == "payment_pending":
        lines.extend(
            [
                "",
                f"Next step: open Stripe Checkout, complete the test payment, then return here and send `confirm order {run.order_id}`.",
            ]
        )

    if run.split.shortfall:
        lines.append(f"- Shortfall: {run.split.shortfall} {run.intent.item}")
    if run.split.over_budget and run.intent.budget is not None:
        lines.append(f"- Over budget by: {_format_money(run.split.total_cost - run.intent.budget, currency)}")

    return "\n".join(lines)


def _is_paid_stripe_confirmation(run: ProcurementRun) -> bool:
    return (
        run.status == "confirmed"
        and run.buyer_funding.provider == "stripe"
        and run.buyer_funding.status == "paid"
        and not run.buyer_funding.simulated
        and bool(run.settlements)
    )


def _is_unpaid_stripe_confirmation(run: ProcurementRun) -> bool:
    return (
        run.status == "payment_pending"
        and run.buyer_funding.provider == "stripe"
        and not run.buyer_funding.simulated
        and not run.quotes
        and not run.settlements
    )


def _format_paid_stripe_confirmation(run: ProcurementRun, currency: str) -> str:
    settlements_by_seller = {
        settlement.allocation.seller: settlement for settlement in run.settlements
    }
    allocation_lines = [
        f"- {_format_allocation_line(allocation, settlements_by_seller.get(allocation.seller), currency)}"
        for allocation in run.split.allocations
    ]
    payment_label = _format_farm_payout_mode(run)

    lines = [
        f"Payment confirmed for order {run.order_id}.",
        "",
        "Final receipt:",
        f"- Item: {run.intent.qty} {run.intent.item}",
        *allocation_lines,
        f"- Total: {_format_money(run.split.total_cost, currency)}",
        f"- Buyer payment: {_format_buyer_funding(run)}",
        f"- Farm payouts: {payment_label}",
        *_format_stripe_step_lines(run, currency),
        *_format_agent_trace_lines(run),
        *_format_fulfillment_lines(run),
    ]
    return "\n".join(lines)


def _format_unpaid_stripe_confirmation(run: ProcurementRun, currency: str) -> str:
    lines = [
        f"Stripe Checkout is not marked paid yet for order {run.order_id}.",
        "",
        "Payment status:",
        f"- Checkout: {run.buyer_funding.status}",
        f"- Amount: {_format_money(run.buyer_funding.amount, currency)}",
        f"- Buyer funding: {_format_buyer_funding(run)}",
        "",
        "Next step: complete the Stripe test payment, then send "
        f"`confirm order {run.order_id}` again.",
    ]
    return "\n".join(lines)


def _format_buyer_funding(run: ProcurementRun) -> str:
    if run.buyer_funding.amount == 0:
        return "not requested"
    if (
        run.buyer_funding.provider == "stripe"
        and run.buyer_funding.status == "paid"
        and not run.buyer_funding.simulated
    ):
        return f"Stripe Checkout paid ({_short_reference(run.buyer_funding.reference)})"
    if run.buyer_funding.checkout_url:
        return f"[Open Stripe Checkout]({run.buyer_funding.checkout_url})"
    return _short_reference(run.buyer_funding.receipt_ref)


def _format_stripe_step_lines(run: ProcurementRun, currency: str) -> list[str]:
    if not _uses_stripe_flow(run) or run.buyer_funding.amount == 0:
        return []

    if run.buyer_funding.status == "paid" and not run.buyer_funding.simulated:
        checkout_status = "confirmed"
    elif run.buyer_funding.simulated:
        checkout_status = "simulated"
    else:
        checkout_status = "created"
    lines = [
        "",
        "Stripe steps:",
        (
            f"- Checkout Session {checkout_status}: {_format_buyer_funding(run)} "
            f"for {_format_money(run.buyer_funding.amount, currency)}"
        ),
    ]

    if run.status == "payment_pending":
        lines.append("- Farm payouts: waiting for Stripe payment confirmation")
        return lines

    for settlement in run.settlements:
        transfer_status = "simulated" if settlement.payment.simulated else "created"
        lines.append(
            f"- Connect transfer {transfer_status}: {_short_reference(settlement.payment.receipt_ref)} "
            f"to {settlement.allocation.seller} Stripe account "
            f"for {_format_money(settlement.payment.amount_fet, currency)}"
        )
    return lines


def _format_fulfillment_lines(run: ProcurementRun) -> list[str]:
    if run.status != "confirmed" or not run.settlements:
        return []
    return [
        "",
        (
            f"Order confirmed. Your {run.intent.qty} {run.intent.item} order has been placed "
            "and the selected farms will prepare it for shipment shortly."
        ),
    ]


def _format_agent_trace_lines(run: ProcurementRun) -> list[str]:
    trace = [
        line
        for line in run.transcript
        if (
            line.startswith("Registry returned")
            or line.startswith("Sent QuoteRequest")
            or line.startswith("Sent PurchaseOrder")
            or line.startswith("Business Agent quote")
            or line.startswith("Business-only split")
            or line.startswith("Business Agent live reply timed out")
            or "through live agent messages" in line
            or "Business Agent" in line and line.startswith("Done:")
        )
    ]
    if not trace:
        return []
    return ["", "Agent trace:", *[f"- {line}" for line in trace]]


def _uses_stripe_flow(run: ProcurementRun) -> bool:
    return (
        run.buyer_payment_mode == STRIPE_BUYER_PAYMENT_MODE
        or run.payment_mode == STRIPE_CONNECT_FARM_PAYMENT_MODE
    )


def _overlay_business_quote(
    quotes: list[Quote],
    business_quote: Quote,
    sellers: list[FarmState],
    item: str,
) -> tuple[list[Quote], Quote | None]:
    """Replace a matching seller's quote with a live Business Agent quote.

    Only applies when the live quote's seller already exists as a farm (so settlement
    stays valid), and clamps the live quantity to that farm's real stock so fulfillment
    can never exceed inventory. Returns the (possibly unchanged) quotes plus the applied
    quote (or None if it was not applied).
    """

    farm = next((f for f in sellers if f.name == business_quote.seller), None)
    if farm is None or item not in farm.catalog:
        return quotes, None

    stock = farm.catalog[item].stock
    qty_available = max(0, min(business_quote.qty_available, stock))
    if qty_available <= 0 or business_quote.unit_price <= 0:
        return quotes, None

    applied = Quote(
        seller=farm.name,
        item=item,
        qty_available=qty_available,
        unit_price=business_quote.unit_price,
    )
    updated = [applied if quote.seller == farm.name else quote for quote in quotes]
    return updated, applied


def _is_checkout_pending(funding: BuyerFundingResult) -> bool:
    return (
        funding.provider == "stripe"
        and not funding.simulated
        and funding.amount > 0
        and funding.status != "paid"
    )


def _display_currency(run: ProcurementRun) -> str:
    if run.buyer_payment_mode == STRIPE_BUYER_PAYMENT_MODE:
        return "usd"
    if run.payment_mode == STRIPE_CONNECT_FARM_PAYMENT_MODE:
        return "usd"
    return "fet"


def _format_money(amount: float, currency: str) -> str:
    if currency == "usd":
        return f"${amount:.2f}"
    return f"{amount:.2f} FET"


def _format_buyer_payment_mode(run: ProcurementRun) -> str:
    if run.buyer_payment_mode == STRIPE_BUYER_PAYMENT_MODE:
        return "Stripe Checkout (simulated)" if run.buyer_funding.simulated else "Stripe Checkout"
    return run.buyer_funding.provider


def farm_payment_recipient(farm: FarmState, payment_mode: str) -> str:
    if payment_mode == STRIPE_CONNECT_FARM_PAYMENT_MODE and farm.stripe_connected_account_id:
        return farm.stripe_connected_account_id
    return farm.wallet_address


def _format_farm_payout_mode(run: ProcurementRun) -> str:
    if any(settlement.payment.status == "business_agent_confirmed" for settlement in run.settlements):
        return "Business Agent confirmation"
    has_real_payment = any(not settlement.payment.simulated for settlement in run.settlements)
    if run.payment_mode == STRIPE_CONNECT_FARM_PAYMENT_MODE:
        return "Stripe Connect" if has_real_payment else "Stripe Connect (simulated/local demo)"
    if run.payment_mode == TESTNET_PAYMENT_MODE:
        return "testnet FET" if has_real_payment else "testnet FET fallback (simulated/local demo)"
    return "simulated/local demo"


def _format_allocation_line(
    allocation: Allocation,
    settlement: FarmSettlement | None,
    currency: str,
) -> str:
    total = allocation.total_cost
    if settlement is None:
        payment_note = "not paid"
    else:
        payment_note = _short_reference(settlement.payment.receipt_ref)
    return (
        f"{allocation.seller}: {allocation.qty} {allocation.item} = "
        f"{_format_money(total, currency)} ({payment_note})"
    )


def _short_reference(value: str, *, prefix: int = 14, suffix: int = 6) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        return "link"
    if len(value) <= prefix + suffix + 1:
        return value
    return f"{value[:prefix]}...{value[-suffix:]}"
