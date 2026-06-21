from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from agents.workflow import format_procurement_response, run_procurement_locally


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or "I need 500 tomatoes under $250."
    run = run_procurement_locally(
        prompt,
        payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE"),
        intent_mode="local",
    )
    print(format_procurement_response(run))


if __name__ == "__main__":
    main()
