"""Shared message contracts for AgriBroker agents.

The real deployment uses ``uagents.Model``. The small fallback keeps local demos and
unit tests importable before the Fetch dependencies are installed.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - exercised only when uagents is installed.
    from uagents import Model
except Exception:  # pragma: no cover - simple compatibility shim.

    class Model:
        """Tiny subset of pydantic/uAgents model behavior used by local demos."""

        def __init__(self, **kwargs: Any) -> None:
            fields: dict[str, Any] = {}
            for cls in reversed(type(self).__mro__):
                fields.update(getattr(cls, "__annotations__", {}))

            missing: list[str] = []
            for field in fields:
                if field in kwargs:
                    setattr(self, field, kwargs.pop(field))
                elif hasattr(type(self), field):
                    setattr(self, field, getattr(type(self), field))
                else:
                    missing.append(field)

            if missing:
                names = ", ".join(missing)
                raise TypeError(f"Missing required field(s): {names}")

            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self) -> dict[str, Any]:
            return dict(self.__dict__)

        def dict(self) -> dict[str, Any]:
            return self.model_dump()

        def __repr__(self) -> str:
            fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            return f"{type(self).__name__}({fields})"


class CatalogItem(Model):
    name: str
    qty: int
    unit_price: float


class RegisterCatalog(Model):
    address: str
    items: list[CatalogItem]


class WhoSells(Model):
    item: str


class SellerList(Model):
    item: str
    addresses: list[str]


class QuoteRequest(Model):
    item: str
    qty: int
    request_id: str


class QuoteResponse(Model):
    request_id: str
    farmer: str
    item: str
    qty_available: int
    unit_price: float


class PurchaseOrder(Model):
    order_id: str
    item: str
    qty: int
    agreed_unit_price: float


class Invoice(Model):
    order_id: str
    pay_to_address: str
    total_fet: float
    stripe_connected_account_id: str | None = None


class BuyerFundingRequest(Model):
    order_id: str
    pay_to_address: str
    total_fet: float
    description: str


class BuyerFundingConfirmed(Model):
    order_id: str
    tx_hash: str
    amount_fet: float


class PaymentSent(Model):
    order_id: str
    tx_hash: str
    amount_fet: float


class Receipt(Model):
    order_id: str
    status: str
    message: str


class ProcurementRequest(Model):
    text: str


class ProcurementResult(Model):
    status: str
    summary: str
    total_fet: float
