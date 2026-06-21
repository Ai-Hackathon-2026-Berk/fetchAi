from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uagents import Agent

from agents.payments import get_balance_fet
from agents.settings import fetch_network
from agents.workflow import load_farms


ORCHESTRATOR_SEED = "agribroker-orchestrator-demo-seed-change-before-deploy"


def main() -> int:
    orchestrator = Agent(
        name="agribroker",
        seed=ORCHESTRATOR_SEED,
        network=fetch_network(),
    )
    wallet = orchestrator.wallet
    address = str(wallet.address())
    print("AgriBroker testnet payment readiness")
    print("====================================")
    print(f"Network: {fetch_network()}")
    print(f"Orchestrator agent:  {orchestrator.address}")
    print(f"Orchestrator wallet: {address}")

    balance = get_balance_fet(orchestrator._ledger, address)
    if balance is None:
        print("Balance: unknown; uAgents ledger API did not expose a readable balance here.")
    else:
        print(f"Balance: {balance:.6f} FET")

    print()
    print("Farm recipient wallets")
    print("----------------------")
    for farm in load_farms():
        agent = Agent(
            name=farm.name.lower().replace(" ", "_"),
            seed=farm.seed,
            network=fetch_network(),
        )
        print(f"{farm.name}: {agent.wallet.address()}")

    print()
    print("Before enabling AGRIBROKER_PAYMENT_MODE=testnet, fund the orchestrator wallet.")
    print("Note: contract-version warnings during this script are OK; the wallet addresses still derive deterministically from the seeds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
