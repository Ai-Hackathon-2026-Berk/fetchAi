"""Registry uAgent for seller discovery."""

from __future__ import annotations

from collections import defaultdict
import os

from agents.agentverse_profiles import registry_profile_kwargs
from agents.protocols import RegisterCatalog, SellerList, WhoSells
from agents.settings import fetch_network

try:  # pragma: no cover - requires uagents runtime.
    from uagents import Agent, Context, Protocol
except Exception:  # pragma: no cover
    Agent = None  # type: ignore[assignment]
    Context = object  # type: ignore[assignment]
    Protocol = None  # type: ignore[assignment]


def create_registry_agent(seed: str, port: int = 8100, *, local_only: bool = False):
    if Agent is None:
        raise RuntimeError("uagents is not installed. Install requirements.txt first.")

    # local_only skips the Agentverse mailbox/profile so the registry talks purely over
    # local endpoints (used by the live bureau demo to avoid Agentverse rate limits).
    profile = {} if local_only else registry_profile_kwargs()
    registry = Agent(
        name="agribroker_registry",
        seed=seed,
        port=port,
        network=fetch_network(),
        **profile,
    )
    sellers_by_item: dict[str, set[str]] = defaultdict(set)
    registry_protocol = Protocol(name="AgriBrokerRegistryProtocol", version="1.0")

    @registry.on_event("startup")
    async def announce(ctx: Context) -> None:
        ctx.logger.info(f"Registry agent address: {ctx.agent.address}")

    @registry_protocol.on_message(model=RegisterCatalog)
    async def register_catalog(ctx: Context, sender: str, msg: RegisterCatalog) -> None:
        for item in msg.items:
            sellers_by_item[item.name.lower()].add(msg.address)
        ctx.logger.info(f"Registered catalog for {sender}: {msg.items}")

    @registry_protocol.on_message(model=WhoSells, replies=SellerList)
    async def who_sells(ctx: Context, sender: str, msg: WhoSells) -> None:
        item = msg.item.lower()
        await ctx.send(sender, SellerList(item=item, addresses=sorted(sellers_by_item[item])))

    registry.include(registry_protocol, publish_manifest=not local_only)
    return registry


if __name__ == "__main__":  # pragma: no cover
    create_registry_agent(
        os.getenv("REGISTRY_SEED", "agribroker-registry-demo-seed-change-before-deploy"),
        port=int(os.getenv("REGISTRY_PORT", "8100")),
    ).run()
