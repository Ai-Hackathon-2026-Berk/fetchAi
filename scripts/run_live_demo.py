"""Live AgriBroker demo: real agent-to-agent conversations in a local Bureau.

This runs the Registry, all Farmer agents, and a buyer/orchestrator agent together
and triggers a real procurement. Every quote, order, and payment is an actual uAgent
message between separate agents (visible in the logs) — not an in-process function call.

It runs on LOCAL endpoints (no Agentverse mailbox), so there is no hosted proxy and no
rate limiting. The hosted Flockx Business Agent is NOT reached here (that needs Agentverse);
show Sunny Acres live in ASI:One instead.

Run:  python scripts/run_live_demo.py
Then watch the logs:  Registry registrations -> QuoteRequests -> PurchaseOrders ->
Invoices -> PaymentSent -> Receipts, ending with the formatted receipt.
"""

import asyncio
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep the live demo offline-payment and deterministic (no Stripe network calls).
os.environ.setdefault("AGRIBROKER_BUYER_PAYMENT_MODE", "simulated")
os.environ.setdefault("AGRIBROKER_FARM_PAYMENT_MODE", "simulated")
os.environ.setdefault("AGRIBROKER_INTENT_MODE", "local")

try:
    from uagents import Agent, Bureau, Context
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Install uAgents first: python -m pip install -r requirements.txt") from exc

from agents.agent_network import run_procurement_via_agents
from agents.farmer_agent import create_farmer_agent
from agents.registry_agent import create_registry_agent
from agents.settings import fetch_network
from agents.workflow import format_procurement_response, load_farms

BUYER_PROMPT = "I need 500 tomatoes under $250."


def main() -> None:
    registry = create_registry_agent(
        "agribroker-registry-demo-seed-change-before-deploy", local_only=True
    )
    farms = [
        create_farmer_agent(farm, registry_address=registry.address, local_only=True)
        for farm in load_farms()
    ]
    orchestrator = Agent(
        name="agribroker_buyer",
        seed="agribroker-live-demo-buyer-seed-change-before-deploy",
        port=8200,
        network=fetch_network(),
    )

    @orchestrator.on_event("startup")
    async def run_demo(ctx: Context) -> None:
        await asyncio.sleep(4)  # give the farmer agents a moment to register
        ctx.logger.info("=============== BUYER REQUEST ===============")
        ctx.logger.info(BUYER_PROMPT)
        try:
            run = await run_procurement_via_agents(
                ctx=ctx,
                registry_address=registry.address,
                buyer_text=BUYER_PROMPT,
                payment_mode="simulated",
                intent_mode="local",
                wallet=orchestrator.wallet,
            )
        except Exception as exc:
            ctx.logger.error(f"Live procurement failed: {exc}")
            return

        ctx.logger.info("=========== LIVE AGENT CONVERSATION ===========")
        for line in run.transcript:
            ctx.logger.info(line)
        ctx.logger.info("================== RECEIPT ==================")
        print("\n" + format_procurement_response(run) + "\n")

    bureau = Bureau(port=8100, endpoint=["http://127.0.0.1:8100/submit"], network=fetch_network())
    bureau.add(registry)
    for farm in farms:
        bureau.add(farm)
    bureau.add(orchestrator)

    print("Starting AgriBroker LIVE demo — real agent-to-agent messages (local, no Agentverse)")
    print(f"Registry         : {registry.address}")
    for farm in farms:
        print(f"Farm {farm.name:<14}: {farm.address}")
    print(f"Buyer/Orchestrator: {orchestrator.address}")
    print("\nWatch the logs below for the live conversation...\n")
    bureau.run()


if __name__ == "__main__":
    main()
