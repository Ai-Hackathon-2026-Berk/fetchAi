"""Pure order-splitting optimizer for AgriBroker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Quote:
    seller: str
    item: str
    qty_available: int
    unit_price: float


@dataclass(frozen=True, slots=True)
class Allocation:
    seller: str
    item: str
    qty: int
    unit_price: float

    @property
    def total_cost(self) -> float:
        return round(self.qty * self.unit_price, 6)


@dataclass(frozen=True, slots=True)
class SplitResult:
    item: str
    requested_qty: int
    allocated_qty: int
    total_cost: float
    allocations: tuple[Allocation, ...]
    shortfall: int = 0
    over_budget: bool = False
    budget: float | None = None

    @property
    def fulfilled(self) -> bool:
        return self.shortfall == 0


def optimize_split(
    quotes: list[Quote],
    qty_needed: int,
    budget: float | None = None,
) -> SplitResult:
    """Return the cheapest allocation across sellers.

    Because each unit has only a per-unit price and there are no fixed costs, sorting
    by unit price and filling greedily is optimal.
    """

    if qty_needed <= 0:
        raise ValueError("qty_needed must be greater than zero")
    if budget is not None and budget < 0:
        raise ValueError("budget cannot be negative")

    valid_quotes = [
        quote
        for quote in quotes
        if quote.qty_available > 0 and quote.unit_price >= 0
    ]
    if not valid_quotes:
        item = quotes[0].item if quotes else ""
        return SplitResult(
            item=item,
            requested_qty=qty_needed,
            allocated_qty=0,
            total_cost=0.0,
            allocations=(),
            shortfall=qty_needed,
            budget=budget,
        )

    item = valid_quotes[0].item
    remaining = qty_needed
    allocations: list[Allocation] = []

    for quote in sorted(valid_quotes, key=lambda q: (q.unit_price, q.seller)):
        if remaining == 0:
            break

        take_qty = min(remaining, quote.qty_available)
        allocations.append(
            Allocation(
                seller=quote.seller,
                item=quote.item,
                qty=take_qty,
                unit_price=quote.unit_price,
            )
        )
        remaining -= take_qty

    total_cost = round(sum(allocation.total_cost for allocation in allocations), 6)
    return SplitResult(
        item=item,
        requested_qty=qty_needed,
        allocated_qty=qty_needed - remaining,
        total_cost=total_cost,
        allocations=tuple(allocations),
        shortfall=remaining,
        over_budget=budget is not None and total_cost > budget,
        budget=budget,
    )

