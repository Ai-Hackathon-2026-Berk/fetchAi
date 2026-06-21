"""One-command AgriBroker showcase: marketplace + onboarding + Business Agent.

Runs fully offline and deterministically (no Agentverse, no live network, no rate
limits) so it is safe to screen-record. It exercises the real code paths:

  1. The marketplace optimizing and paying across multiple farms.
  2. A new farmer self-onboarding and immediately competing.
  3. AgriBroker parsing a real Flockx Business Agent reply and using it live.

Run:  python scripts/showcase.py
"""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force a clean, offline, deterministic run regardless of any .env / shell config.
os.environ["AGRIBROKER_INTENT_MODE"] = "local"
os.environ["AGRIBROKER_BUYER_PAYMENT_MODE"] = "simulated"
os.environ["AGRIBROKER_FARM_PAYMENT_MODE"] = "simulated"

from agents.business_seller import quote_from_reply
from agents.farm_state import FarmState
from agents.onboarding import onboard_farmer
from agents.workflow import format_procurement_response, load_farms, run_procurement_locally

# The actual natural-language reply the Sunny Acres Business Agent returns in ASI:One.
SUNNY_ACRES_REPLY = (
    "Sunny Acres can supply 300 tomatoes at $0.48 each (total $144.00). "
    "We have plenty in stock — ready to go when you are!"
)


def _banner(number: int, title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {number}. {title}")
    print("=" * 72)


def _transcript_line(run, needle: str) -> None:
    for line in run.transcript:
        if needle in line:
            print(f"   ↳ {line}")


def part_marketplace() -> None:
    _banner(1, "THE MARKETPLACE — one request, five farms, cheapest split")
    print('Buyer asks: "I need 500 tomatoes under $250."\n')
    run = run_procurement_locally("I need 500 tomatoes under $250.")
    print(format_procurement_response(run))


def part_onboarding() -> None:
    _banner(2, "FARMER ONBOARDING — a new seller joins and immediately competes")
    farms = load_farms()
    result = onboard_farmer(
        name="Hilltop Farm",
        items=[{"item": "tomatoes", "stock": 250, "base_unit_price": 0.38, "price_floor": 0.35}],
        personality="Brand-new self-onboarded grower, undercutting to win its first orders.",
        existing_ports=[farm.port for farm in farms],
        seed_suffix="showcase",
    )
    entry = result.farm_entry
    print(
        f'New farmer onboarded: "{entry["name"]}" — tomatoes @ '
        f'${entry["catalog"]["tomatoes"]["base_unit_price"]:.2f} '
        f'(port {entry["port"]}, Stripe {result.stripe.account_id})'
    )
    print("Re-running the same order with the new seller in the market:\n")
    farms.append(FarmState.from_config(entry))
    run = run_procurement_locally("I need 500 tomatoes under $250.", farms=farms)
    print(format_procurement_response(run))


def part_business_agent() -> None:
    _banner(3, "REAL FETCH BUSINESS AGENT — Sunny Acres quotes live over Chat Protocol")
    print("Sunny Acres (a verified Flockx Business Agent) replied in natural language:")
    print(f'   "{SUNNY_ACRES_REPLY}"\n')
    quote = quote_from_reply(SUNNY_ACRES_REPLY, qty=1000, item="tomatoes")
    print(
        f"AgriBroker parsed that reply → {quote.seller}: "
        f"{quote.qty_available} @ ${quote.unit_price:.2f}, and fed it into the optimizer.\n"
    )
    print('Buyer asks: "I need 1000 tomatoes under $500."\n')
    run = run_procurement_locally("I need 1000 tomatoes under $500.", business_quote=quote)
    print(format_procurement_response(run))
    _transcript_line(run, "Live Business Agent quote")


def main() -> None:
    print("\nAgriBroker — autonomous produce procurement (offline showcase)")
    part_marketplace()
    part_onboarding()
    part_business_agent()
    print("\n" + "-" * 72)
    print("Marketplace + onboarding + live Business Agent quote — one run, no live infra.")
    print("-" * 72 + "\n")


if __name__ == "__main__":
    main()
