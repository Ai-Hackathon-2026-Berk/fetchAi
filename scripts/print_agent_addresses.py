from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uagents import Agent

from agents.settings import fetch_network
from agents.workflow import load_farms


def wallet_address(agent: Agent) -> str:
    return str(agent.wallet.address())


def main() -> None:
    print("AgriBroker agent addresses")
    print("==========================")
    print("Note: contract-version warnings are OK; addresses still derive deterministically from seeds.")
    print()

    registry = Agent(
        name="agribroker_registry",
        seed="agribroker-registry-demo-seed-change-before-deploy",
        network=fetch_network(),
    )
    orchestrator = Agent(
        name="agribroker",
        seed="agribroker-orchestrator-demo-seed-change-before-deploy",
        network=fetch_network(),
    )
    print(f"Registry agent:      {registry.address}")
    print(f"Registry wallet:     {wallet_address(registry)}")
    print(f"Orchestrator agent:  {orchestrator.address}")
    print(f"Orchestrator wallet: {wallet_address(orchestrator)}")
    print()
    print("Farm agents")
    print("-----------")
    for farm in load_farms():
        agent = Agent(
            name=farm.name.lower().replace(" ", "_"),
            seed=farm.seed,
            network=fetch_network(),
        )
        print(f"{farm.name}:")
        print(f"  agent:  {agent.address}")
        print(f"  wallet: {wallet_address(agent)}")


if __name__ == "__main__":
    main()
