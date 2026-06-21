"""Run the FULL live multi-agent system behind ASI:One — in one Bureau.

This hosts the AgriBroker chat agent (the ASI:One entry point, with a mailbox) together
with the Registry and all Farmer agents in a single Bureau. When a buyer chats from
ASI:One:

  - the message reaches the chat agent via its mailbox (the only Agentverse connection),
  - the chat agent then talks to the Registry and Farmer agents *locally inside the
    bureau* — real uAgent messages, but routed locally, so there is NO Agentverse proxy
    traffic and NO rate limiting on the agent-to-agent conversation.

So the live agent conversation runs end to end through ASI:One, reliably.

Run:  python scripts/run_asi_live_demo.py
Then connect ONLY the chat agent's mailbox from its Inspector URL, and chat via ASI:One.
The agent-to-agent conversation prints in this terminal as it happens.
"""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from uagents import Bureau
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Install uAgents first: python -m pip install -r requirements.txt") from exc

from agents.farmer_agent import create_farmer_agent
from agents.registry_agent import create_registry_agent
from agents.settings import fetch_network
from agents.workflow import load_farms

REGISTRY_SEED = "agribroker-registry-demo-seed-change-before-deploy"


def main() -> None:
    # Registry + farmers run locally inside the bureau (no Agentverse mailbox).
    registry = create_registry_agent(REGISTRY_SEED, local_only=True)
    farms = [
        create_farmer_agent(farm, registry_address=registry.address, local_only=True)
        for farm in load_farms()
    ]

    # Point the chat agent at the in-bureau registry, in live agent mode. These are set
    # before create_asi_chat_agent() reads them at message time, and override any .env.
    os.environ["AGRIBROKER_DISCOVERY_MODE"] = "agent"
    os.environ["AGRIBROKER_REGISTRY_ADDRESS"] = registry.address

    # Import after setting env so load_dotenv() in the module can't shadow our overrides
    # for discovery/registry (we re-assert them above anyway).
    from agents.asi_chat_agent import create_asi_chat_agent

    os.environ["AGRIBROKER_DISCOVERY_MODE"] = "agent"
    os.environ["AGRIBROKER_REGISTRY_ADDRESS"] = registry.address

    chat = create_asi_chat_agent()  # mailbox=True — the ASI:One entry point

    bureau = Bureau(port=8100, endpoint=["http://127.0.0.1:8100/submit"], network=fetch_network())
    bureau.add(registry)
    for farm in farms:
        bureau.add(farm)
    bureau.add(chat)

    print("AgriBroker — LIVE multi-agent system behind ASI:One (one bureau)")
    print(f"Registry        : {registry.address}")
    for farm in farms:
        print(f"Farm {farm.name:<14}: {farm.address}")
    print(f"Chat agent      : {chat.address}")
    print("\n>>> Connect ONLY the chat agent's mailbox from its Inspector URL below,")
    print(">>> then chat from ASI:One. The agent conversation prints here.\n")
    bureau.run()


if __name__ == "__main__":
    main()
