from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.workflow import run_procurement_locally


def main() -> None:
    run = run_procurement_locally("I need 500 tomatoes under 250 FET.")
    print("AgriBroker local demo")
    print("====================")
    for line in run.transcript:
        print(f"- {line}")


if __name__ == "__main__":
    main()
