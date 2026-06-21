from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.agentverse_profiles import (
    farmer_profile_kwargs,
    orchestrator_profile_kwargs,
    registry_profile_kwargs,
)
from agents.workflow import load_farms


def main() -> None:
    print("AgriBroker Agentverse profiles")
    print("==============================")
    _print_profile(
        "AgriBroker Chat",
        "@agribroker",
        "docs/agentverse-profile.md",
        "python -m agents.asi_chat_agent",
    )

    registry = registry_profile_kwargs()
    _print_profile(
        "Registry",
        f"@{registry['handle']}",
        registry.get("readme_path"),
        "python -m agents.registry_agent",
    )

    orchestrator = orchestrator_profile_kwargs()
    _print_profile(
        "Structured Orchestrator",
        f"@{orchestrator['handle']}",
        orchestrator.get("readme_path"),
        "python -m agents.orchestrator_agent",
    )

    for farm in load_farms():
        profile = farmer_profile_kwargs(farm)
        _print_profile(
            farm.name,
            f"@{profile['handle']}",
            profile.get("readme_path"),
            f'python -m agents.farmer_agent --name "{farm.name}" --registry <REGISTRY_ADDRESS>',
        )


def _print_profile(name: str, handle: str, readme_path: object, command: str) -> None:
    print()
    print(name)
    print("-" * len(name))
    print(f"Handle: {handle}")
    print(f"README: {readme_path or '(missing)'}")
    print(f"Run: {command}")


if __name__ == "__main__":
    main()
