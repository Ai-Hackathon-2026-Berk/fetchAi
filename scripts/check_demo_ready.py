from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass


def run_check(name: str, command: list[str]) -> bool:
    print(f"\n{name}")
    print("-" * len(name))
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    print("PASS" if result.returncode == 0 else "FAIL")
    if result.returncode != 0 and "uAgents Chat Protocol" in name:
        print("\nInstall the Fetch chat dependencies into this Python environment:")
        print(f"{sys.executable} -m pip install -r requirements.txt")
    return result.returncode == 0


def main() -> int:
    checks = [
        ("Unit tests", [sys.executable, "-m", "pytest"]),
        ("ASI response preview", [sys.executable, "scripts/preview_asi_response.py"]),
        (
            "uAgents Chat Protocol imports",
            [
                sys.executable,
                "-c",
                (
                    "from uagents_core.contrib.protocols.chat import ChatMessage; "
                    "from agents.asi_chat_agent import create_asi_chat_agent; "
                    "print('imports ok')"
                ),
            ],
        ),
    ]
    ok = all(run_check(name, command) for name, command in checks)

    print("\nLive setup")
    print("----------")
    print(f"AGRIBROKER_INTENT_MODE={os.getenv('AGRIBROKER_INTENT_MODE', 'local')}")
    print(f"AGRIBROKER_DISCOVERY_MODE={os.getenv('AGRIBROKER_DISCOVERY_MODE', 'local')}")
    print(
        "AGRIBROKER_REGISTRY_ADDRESS=set"
        if os.getenv("AGRIBROKER_REGISTRY_ADDRESS")
        else "AGRIBROKER_REGISTRY_ADDRESS=missing"
    )
    print(f"AGRIBROKER_BUYER_PAYMENT_MODE={os.getenv('AGRIBROKER_BUYER_PAYMENT_MODE', 'simulated')}")
    print(f"AGRIBROKER_FARM_PAYMENT_MODE={os.getenv('AGRIBROKER_FARM_PAYMENT_MODE', 'simulated')}")
    print("STRIPE_SECRET_KEY=set" if os.getenv("STRIPE_SECRET_KEY") else "STRIPE_SECRET_KEY=missing")
    print(f"STRIPE_SUCCESS_URL={os.getenv('STRIPE_SUCCESS_URL', 'https://example.com/agribroker/success')}")
    print(f"STRIPE_CANCEL_URL={os.getenv('STRIPE_CANCEL_URL', 'https://example.com/agribroker/cancel')}")
    print(f"FETCH_NETWORK={os.getenv('FETCH_NETWORK', 'testnet')}")
    print("ASI_ONE_API_KEY=set" if os.getenv("ASI_ONE_API_KEY") else "ASI_ONE_API_KEY=missing")
    print("Agentverse mailbox: create/connect manually from the Inspector URL.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
