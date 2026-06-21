"""Parameterized farmer uAgent."""

from __future__ import annotations

import json
from pathlib import Path
import argparse

from agents.farm_state import FarmState
from agents.settings import fetch_network
from agents.protocols import (
    CatalogItem,
    Invoice,
    PaymentSent,
    PurchaseOrder,
    QuoteRequest,
    QuoteResponse,
    Receipt,
    RegisterCatalog,
)

try:  # pragma: no cover - requires uagents runtime.
    from uagents import Agent, Context
except Exception:  # pragma: no cover
    Agent = None  # type: ignore[assignment]
    Context = object  # type: ignore[assignment]


def create_farmer_agent(state: FarmState, registry_address: str | None = None):
    if Agent is None:
        raise RuntimeError("uagents is not installed. Install requirements.txt first.")

    farmer = Agent(
        name=state.name.lower().replace(" ", "_"),
        seed=state.seed,
        port=state.port,
        endpoint=[f"http://127.0.0.1:{state.port}/submit"],
        network=fetch_network(),
    )
    pending_orders: dict[str, PurchaseOrder] = {}

    @farmer.on_event("startup")
    async def startup(ctx: Context) -> None:
        state.wallet_address = str(farmer.wallet.address())
        ctx.logger.info(f"{state.name} agent address: {ctx.agent.address}")
        ctx.logger.info(f"{state.name} wallet address: {state.wallet_address}")
        if registry_address:
            items = [
                CatalogItem(name=item, qty=entry.stock, unit_price=entry.base_unit_price)
                for item, entry in state.catalog.items()
            ]
            await ctx.send(registry_address, RegisterCatalog(address=ctx.agent.address, items=items))

    @farmer.on_message(model=QuoteRequest, replies=QuoteResponse)
    async def quote(ctx: Context, sender: str, msg: QuoteRequest) -> None:
        try:
            response = state.quote(msg.item, msg.qty)
            await ctx.send(
                sender,
                QuoteResponse(
                    request_id=msg.request_id,
                    farmer=state.name,
                    item=response.item,
                    qty_available=response.qty_available,
                    unit_price=response.unit_price,
                ),
            )
        except Exception as exc:
            ctx.logger.warning(f"{state.name} could not quote {msg.item}: {exc}")

    @farmer.on_message(model=PurchaseOrder, replies=Invoice)
    async def invoice(ctx: Context, sender: str, msg: PurchaseOrder) -> None:
        total = state.invoice_total(msg.item, msg.qty, msg.agreed_unit_price)
        pending_orders[msg.order_id] = msg
        await ctx.send(
            sender,
            Invoice(
                order_id=msg.order_id,
                pay_to_address=state.wallet_address,
                total_fet=total,
                stripe_connected_account_id=state.stripe_connected_account_id,
            ),
        )

    @farmer.on_message(model=PaymentSent, replies=Receipt)
    async def confirm_payment(ctx: Context, sender: str, msg: PaymentSent) -> None:
        order = pending_orders.get(msg.order_id)
        if order is None:
            await ctx.send(sender, Receipt(order_id=msg.order_id, status="failed", message="Unknown order"))
            return

        state.fulfill(order.item, order.qty)
        await ctx.send(
            sender,
            Receipt(
                order_id=msg.order_id,
                status="confirmed",
                message=f"{state.name} reserved {order.qty} {order.item}; tx={msg.tx_hash}",
            ),
        )

    return farmer


def load_farm_state(name: str, config_path: Path = Path("config/farms.json")) -> FarmState:
    payload = json.loads(config_path.read_text())
    for farm in payload["farms"]:
        if farm["name"].lower() == name.lower():
            return FarmState.from_config(farm)
    raise KeyError(f"No farm named {name}")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Run a single AgriBroker farmer agent.")
    parser.add_argument("--name", default="Farm A", help="Farm name from config/farms.json")
    parser.add_argument("--registry", default=None, help="Optional registry agent address")
    args = parser.parse_args()

    farm_state = load_farm_state(args.name)
    create_farmer_agent(farm_state, registry_address=args.registry).run()
