"""Local pending-order storage for Stripe Checkout confirmation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ORDER_STORE = Path(".agribroker_pending_orders.json")


@dataclass(frozen=True, slots=True)
class PendingOrder:
    order_id: str
    buyer_text: str
    checkout_session_id: str
    amount: float
    currency: str


def save_pending_order(order: PendingOrder, path: Path = DEFAULT_ORDER_STORE) -> None:
    payload = _read_store(path)
    payload[order.order_id] = {
        "order_id": order.order_id,
        "buyer_text": order.buyer_text,
        "checkout_session_id": order.checkout_session_id,
        "amount": order.amount,
        "currency": order.currency,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_pending_order(order_id: str, path: Path = DEFAULT_ORDER_STORE) -> PendingOrder | None:
    raw = _read_store(path).get(order_id)
    if not isinstance(raw, dict):
        return None
    return PendingOrder(
        order_id=str(raw["order_id"]),
        buyer_text=str(raw["buyer_text"]),
        checkout_session_id=str(raw["checkout_session_id"]),
        amount=float(raw["amount"]),
        currency=str(raw["currency"]),
    )


def latest_pending_order(path: Path = DEFAULT_ORDER_STORE) -> PendingOrder | None:
    payload = _read_store(path)
    if not payload:
        return None
    last_key = next(reversed(payload))
    return load_pending_order(last_key, path=path)


def delete_pending_order(order_id: str, path: Path = DEFAULT_ORDER_STORE) -> None:
    payload = _read_store(path)
    if order_id in payload:
        del payload[order_id]
        path.write_text(json.dumps(payload, indent=2) + "\n")


def _read_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
