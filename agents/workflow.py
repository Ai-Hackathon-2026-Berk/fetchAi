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
) -> ProcurementRun:
    order_id = f"order-{uuid4().hex[:8]}"
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

    quotes = tuple(farm.quote(intent.item, intent.qty) for farm in sellers)
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


def format_procurement_response(run: ProcurementRun) -> str:
    currency = _display_currency(run)
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
    ]

    if run.split.shortfall:
        lines.append(f"- Shortfall: {run.split.shortfall} {run.intent.item}")
    if run.split.over_budget and run.intent.budget is not None:
        lines.append(f"- Over budget by: {_format_money(run.split.total_cost - run.intent.budget, currency)}")

    return "\n".join(lines)


def _format_buyer_funding(run: ProcurementRun) -> str:
    if run.buyer_funding.amount == 0:
        return "not requested"
    return run.buyer_funding.receipt_ref


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
        payment_note = settlement.payment.receipt_ref
    return (
        f"{allocation.seller}: {allocation.qty} {allocation.item} = "
        f"{_format_money(total, currency)} ({payment_note})"
    )
