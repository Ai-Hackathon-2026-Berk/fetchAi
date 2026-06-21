"""End-to-end procurement workflow used by the orchestrator and local demo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.farm_state import FarmState
from agents.llm import BuyerIntent, parse_buyer_intent
from agents.optimizer import Allocation, Quote, SplitResult, optimize_split
from agents.payments import (
    PaymentResult,
    get_payment_mode,
    settle_farm_payment,
    simulated_payment,
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
    buyer_funding: PaymentResult
    settlements: tuple[FarmSettlement, ...]
    transcript: tuple[str, ...]
    payment_mode: str

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
    ledger: Any | None = None,
    wallet: Any | None = None,
) -> ProcurementRun:
    import asyncio

    return asyncio.run(
        run_procurement(
            buyer_text,
            farms=farms,
            payment_mode=payment_mode,
            ledger=ledger,
            wallet=wallet,
        )
    )


async def run_procurement(
    buyer_text: str,
    *,
    farms: list[FarmState] | None = None,
    payment_mode: str | None = None,
    ledger: Any | None = None,
    wallet: Any | None = None,
) -> ProcurementRun:
    order_id = f"order-{uuid4().hex[:8]}"
    mode = get_payment_mode(payment_mode)
    farms = farms or load_farms()
    intent = parse_buyer_intent(buyer_text, use_mock=True)
    transcript = [
        f"Buyer intent parsed: {intent.qty} {intent.item}"
        + (f" under {intent.budget:.2f} FET." if intent.budget is not None else ".")
    ]

    sellers = [farm for farm in farms if farm.has_item(intent.item)]
    transcript.append(f"Found {len(sellers)} sellers for {intent.item}.")

    quotes = tuple(farm.quote(intent.item, intent.qty) for farm in sellers)
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
        buyer_funding = simulated_payment(
            order_id=order_id,
            recipient="orchestrator_wallet",
            amount_fet=0.0,
            reason=f"no buyer funding requested: {reason}",
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
        )

    buyer_funding = simulated_payment(
        order_id=order_id,
        recipient="orchestrator_wallet",
        amount_fet=split.total_cost,
        reason="buyer funding is simulated/pre-funded for hackathon reliability",
    )
    transcript.append(
        f"Buyer funded orchestrator: {buyer_funding.amount_fet:.2f} FET "
        f"({buyer_funding.tx_hash})."
    )

    settlements: list[FarmSettlement] = []
    farms_by_name = {farm.name: farm for farm in farms}
    for allocation in split.allocations:
        farm = farms_by_name[allocation.seller]
        total = farm.invoice_total(allocation.item, allocation.qty, allocation.unit_price)
        payment = await settle_farm_payment(
            order_id=order_id,
            recipient=farm.wallet_address,
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
            f"Paid {farm.name}: {total:.2f} FET ({payment.tx_hash}); "
            f"{receipt_message}"
        )

    if split.shortfall:
        transcript.append(f"Shortfall: {split.shortfall} {intent.item}.")
    elif split.over_budget:
        transcript.append(
            f"Plan exceeds budget by {split.total_cost - (intent.budget or 0):.2f} FET."
        )
    else:
        transcript.append(f"Done: {intent.qty} {intent.item} sourced for {split.total_cost:.2f} FET.")

    return ProcurementRun(
        order_id=order_id,
        intent=intent,
        quotes=quotes,
        split=split,
        buyer_funding=buyer_funding,
        settlements=tuple(settlements),
        transcript=tuple(transcript),
        payment_mode=mode,
    )


def format_procurement_response(run: ProcurementRun) -> str:
    quote_lines = [
        f"{quote.seller}: {quote.qty_available} @ {quote.unit_price:.2f} FET"
        for quote in run.quotes
    ]
    settlements_by_seller = {
        settlement.allocation.seller: settlement for settlement in run.settlements
    }
    allocation_lines = [
        _format_allocation_line(allocation, settlements_by_seller.get(allocation.seller))
        for allocation in run.split.allocations
    ]
    budget = "none" if run.intent.budget is None else f"{run.intent.budget:.2f} FET"
    payment_label = (
        "testnet FET"
        if any(not settlement.payment.simulated for settlement in run.settlements)
        else "simulated/local demo"
    )

    lines = [
        f"AgriBroker found {len(run.quotes)} sellers for {run.intent.item}.",
        "",
        "Quotes:",
        *quote_lines,
        "",
        "Optimal split:",
        *allocation_lines,
        "",
        f"Total: {run.split.total_cost:.2f} FET",
        f"Budget: {budget}",
        f"Status: {run.status}",
        f"Payment mode: {payment_label}",
        f"Buyer funding: {run.buyer_funding.tx_hash}",
    ]

    if run.split.shortfall:
        lines.append(f"Shortfall: {run.split.shortfall} {run.intent.item}")
    if run.split.over_budget and run.intent.budget is not None:
        lines.append(f"Over budget by: {run.split.total_cost - run.intent.budget:.2f} FET")

    return "\n".join(lines)


def _format_allocation_line(
    allocation: Allocation,
    settlement: FarmSettlement | None,
) -> str:
    total = allocation.total_cost
    if settlement is None:
        payment_note = "not paid"
    else:
        payment_note = settlement.payment.tx_hash
    return (
        f"{allocation.seller}: {allocation.qty} {allocation.item} = "
        f"{total:.2f} FET ({payment_note})"
    )
