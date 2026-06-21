"""Orchestrator uAgent entry point.

This file exposes a structured uAgent interface now. The ASI:One Chat Protocol
adapter should call the same ``run_procurement_locally``/workflow core once the
current hosted Chat Protocol details are confirmed.
"""

from __future__ import annotations

import os

from agents.agent_network import run_procurement_via_agents
from agents.agentverse_profiles import orchestrator_profile_kwargs
from agents.protocols import ProcurementRequest, ProcurementResult
from agents.settings import discovery_mode, fetch_network, registry_address
from agents.workflow import run_procurement

try:  # pragma: no cover - requires uagents runtime.
    from uagents import Agent, Context
except Exception:  # pragma: no cover
    Agent = None  # type: ignore[assignment]
    Context = object  # type: ignore[assignment]


def create_orchestrator_agent(seed: str, port: int = 8201):
    if Agent is None:
        raise RuntimeError("uagents is not installed. Install requirements.txt first.")

    orchestrator = Agent(
        name="agribroker_orchestrator",
        seed=seed,
        port=port,
        network=fetch_network(),
        **orchestrator_profile_kwargs(),
    )

    @orchestrator.on_event("startup")
    async def startup(ctx: Context) -> None:
        ctx.logger.info(f"AgriBroker orchestrator address: {ctx.agent.address}")
        ctx.logger.info(f"AgriBroker orchestrator wallet: {orchestrator.wallet.address()}")

    @orchestrator.on_message(model=ProcurementRequest, replies=ProcurementResult)
    async def handle_procurement(ctx: Context, sender: str, msg: ProcurementRequest) -> None:
        try:
            mode = discovery_mode()
            address = registry_address()
            if mode == "agent" and address:
                run = await run_procurement_via_agents(
                    ctx=ctx,
                    registry_address=address,
                    buyer_text=msg.text,
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    wallet=orchestrator.wallet,
                )
            else:
                run = await run_procurement(
                    msg.text,
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    ledger=getattr(ctx, "ledger", None),
                    wallet=orchestrator.wallet,
                )
            await ctx.send(
                sender,
                ProcurementResult(
                    status=run.status,
                    summary="\n".join(run.transcript),
                    total_fet=run.split.total_cost,
                ),
            )
        except Exception as exc:
            await ctx.send(
                sender,
                ProcurementResult(status="failed", summary=str(exc), total_fet=0.0),
            )

    return orchestrator


if __name__ == "__main__":  # pragma: no cover
    create_orchestrator_agent(
        os.getenv("STRUCTURED_ORCHESTRATOR_SEED", "agribroker-orchestrator-demo-seed-change-before-deploy"),
        port=int(os.getenv("STRUCTURED_ORCHESTRATOR_PORT", "8201")),
    ).run()
