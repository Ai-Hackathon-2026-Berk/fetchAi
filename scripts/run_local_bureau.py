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


def main() -> None:
    registry = create_registry_agent("agribroker-registry-demo-seed-change-before-deploy")
    farms = [
        create_farmer_agent(farm, registry_address=registry.address)
        for farm in load_farms()
    ]

    bureau = Bureau(
        port=8100,
        endpoint=["http://127.0.0.1:8100/submit"],
        network=fetch_network(),
    )
    bureau.add(registry)
    for farm in farms:
        bureau.add(farm)

    print("Starting AgriBroker local Bureau")
    print(f"Registry: {registry.address}")
    for farm in farms:
        print(f"Farm: {farm.name} -> {farm.address}")
    bureau.run()


if __name__ == "__main__":
    main()
