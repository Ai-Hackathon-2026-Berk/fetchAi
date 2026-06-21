"""State and pricing behavior shared by farmer agents and the local demo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.optimizer import Quote


@dataclass(slots=True)
class CatalogEntry:
    stock: int
    base_unit_price: float
    price_floor: float


@dataclass(slots=True)
class FarmState:
    name: str
    seed: str
    port: int
    personality: str
    catalog: dict[str, CatalogEntry]
    wallet_address: str
    stripe_connected_account_id: str | None = None

    @classmethod
    def from_config(cls, payload: dict[str, Any]) -> "FarmState":
        catalog = {
            item: CatalogEntry(
                stock=int(values["stock"]),
                base_unit_price=float(values["base_unit_price"]),
                price_floor=float(values["price_floor"]),
            )
            for item, values in payload["catalog"].items()
        }
        simulated_wallet = f"fetch_demo_{payload['name'].lower().replace(' ', '_')}"
        return cls(
            name=str(payload["name"]),
            seed=str(payload["seed"]),
            port=int(payload["port"]),
            personality=str(payload["personality"]),
            catalog=catalog,
            wallet_address=simulated_wallet,
            stripe_connected_account_id=payload.get("stripe_connected_account_id"),
        )

    def has_item(self, item: str) -> bool:
        return normalize_item(item) in self.catalog

    def quote(self, item: str, requested_qty: int) -> Quote:
        item_key = normalize_item(item)
        if requested_qty <= 0:
            raise ValueError("requested_qty must be greater than zero")
        if item_key not in self.catalog:
            raise KeyError(f"{self.name} does not sell {item}")

        entry = self.catalog[item_key]
        return Quote(
            seller=self.name,
            item=item_key,
            qty_available=min(requested_qty, entry.stock),
            unit_price=self.current_unit_price(item_key, requested_qty),
        )

    def current_unit_price(self, item: str, requested_qty: int) -> float:
        entry = self.catalog[normalize_item(item)]
        price = entry.base_unit_price

        if entry.stock < 100:
            price *= 1.08
        elif requested_qty <= entry.stock and requested_qty >= 300:
            price *= 0.98

        return round(max(price, entry.price_floor), 4)

    def invoice_total(self, item: str, qty: int, unit_price: float) -> float:
        if qty <= 0:
            raise ValueError("qty must be greater than zero")
        if normalize_item(item) not in self.catalog:
            raise KeyError(f"{self.name} does not sell {item}")
        return round(qty * unit_price, 6)

    def fulfill(self, item: str, qty: int) -> None:
        item_key = normalize_item(item)
        entry = self.catalog[item_key]
        if qty > entry.stock:
            raise ValueError(f"{self.name} only has {entry.stock} {item_key}")
        entry.stock -= qty


def normalize_item(item: str) -> str:
    return item.strip().lower()
