"""Payment helpers for buyer funding and farm settlement."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

PaymentMode = str

SIMULATED_PAYMENT_MODE = "simulated"
TESTNET_PAYMENT_MODE = "testnet"
VALID_PAYMENT_MODES = {SIMULATED_PAYMENT_MODE, TESTNET_PAYMENT_MODE}


@dataclass(frozen=True, slots=True)
class PaymentResult:
    order_id: str
    recipient: str
    amount_fet: float
    tx_hash: str
    status: str
    simulated: bool = False
    reason: str | None = None


class PaymentError(RuntimeError):
    pass


def get_payment_mode(value: str | None = None) -> PaymentMode:
    mode = (value or os.getenv("AGRIBROKER_PAYMENT_MODE") or SIMULATED_PAYMENT_MODE).strip().lower()
    if mode not in VALID_PAYMENT_MODES:
        raise ValueError(
            f"Unsupported payment mode {mode!r}. Use one of: {', '.join(sorted(VALID_PAYMENT_MODES))}"
        )
    return mode


def simulated_payment(
    order_id: str,
    recipient: str,
    amount_fet: float,
    reason: str | None = None,
) -> PaymentResult:
    return PaymentResult(
        order_id=order_id,
        recipient=recipient,
        amount_fet=amount_fet,
        tx_hash=f"simulated-{uuid4().hex[:16]}",
        status="simulated_confirmed",
        simulated=True,
        reason=reason,
    )


async def send_fet_with_retries(
    *,
    order_id: str,
    ledger: Any,
    wallet: Any,
    recipient: str,
    amount_fet: float,
    denom: str = "atestfet",
    attempts: int = 3,
    retry_delay_seconds: float = 1.0,
    fallback_to_simulated: bool = True,
) -> PaymentResult:
    """Send testnet FET with retries and simulated fallback.

    ``amount_fet`` is converted to integer micro-units for the ledger call. The
    current uAgents guide uses ``ctx.ledger.send_tokens(address, amount, denom,
    wallet)`` with ``atestfet`` for testnet examples.
    """

    last_error: Exception | None = None
    amount_units = int(round(amount_fet * 1_000_000))

    for attempt in range(1, attempts + 1):
        try:
            tx = ledger.send_tokens(recipient, amount_units, denom, wallet)
            if hasattr(tx, "wait_to_complete"):
                tx.wait_to_complete()
            return PaymentResult(
                order_id=order_id,
                recipient=recipient,
                amount_fet=amount_fet,
                tx_hash=str(tx.tx_hash),
                status="real_confirmed",
            )
        except Exception as exc:  # pragma: no cover - requires live ledger.
            last_error = exc
            if attempt < attempts:
                await asyncio.sleep(retry_delay_seconds * attempt)

    if fallback_to_simulated:
        reason = str(last_error) if last_error else "unknown payment failure"
        return simulated_payment(order_id, recipient, amount_fet, reason=reason)

    raise PaymentError(str(last_error) if last_error else "payment failed")


async def settle_farm_payment(
    *,
    order_id: str,
    recipient: str,
    amount_fet: float,
    mode: PaymentMode,
    ledger: Any | None = None,
    wallet: Any | None = None,
    reason: str,
) -> PaymentResult:
    if mode == TESTNET_PAYMENT_MODE and ledger is not None and wallet is not None:
        return await send_fet_with_retries(
            order_id=order_id,
            ledger=ledger,
            wallet=wallet,
            recipient=recipient,
            amount_fet=amount_fet,
            denom=os.getenv("FETCH_DENOM", "atestfet"),
        )

    fallback_reason = reason
    if mode == TESTNET_PAYMENT_MODE:
        fallback_reason = "testnet mode requested, but ledger/wallet runtime was unavailable"

    return simulated_payment(
        order_id=order_id,
        recipient=recipient,
        amount_fet=amount_fet,
        reason=fallback_reason,
    )
