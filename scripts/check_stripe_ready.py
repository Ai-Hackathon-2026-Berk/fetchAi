"""Report Stripe readiness for AgriBroker (buyer Checkout + farm Connect payouts).

Safe to run without any Stripe credentials: every check degrades to the simulated
fallback and prints what is missing for the real path.
"""

from pathlib import Path
import json
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

from agents.onboarding import onboard_stripe_express_account
from agents.payments import create_stripe_checkout_session, create_stripe_connect_transfer

FARMS_CONFIG = ROOT / "config" / "farms.json"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _demo_account_ids() -> list[tuple[str, str]]:
    payload = json.loads(FARMS_CONFIG.read_text())
    return [
        (str(farm.get("name", "?")), str(farm.get("stripe_connected_account_id", "(missing)")))
        for farm in payload.get("farms", [])
    ]


def main() -> int:
    has_key = bool(os.getenv("STRIPE_SECRET_KEY"))
    onboarding_enabled = os.getenv("STRIPE_CONNECT_ONBOARDING_ENABLED", "").strip().lower() == "true"
    transfers_enabled = os.getenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "").strip().lower() == "true"

    print("AgriBroker Stripe readiness")
    print("===========================")
    print(f"STRIPE_SECRET_KEY={'set' if has_key else 'missing'}")
    print(f"STRIPE_CONNECT_ONBOARDING_ENABLED={'true' if onboarding_enabled else 'false'}")
    print(f"STRIPE_CONNECT_TRANSFERS_ENABLED={'true' if transfers_enabled else 'false'}")
    print()

    print("Buyer funding (Stripe Checkout)")
    print("-------------------------------")
    checkout = create_stripe_checkout_session(
        order_id="order-preview",
        item="tomatoes",
        qty=500,
        amount=206.0,
    )
    print(f"Provider: {checkout.provider}")
    print(f"Status: {checkout.status}")
    print(f"Reference: {checkout.reference}")
    if checkout.checkout_url:
        print(f"Checkout URL: {checkout.checkout_url}")
    if checkout.reason:
        print(f"Reason: {checkout.reason}")
    print(f"Live Checkout ready: {_yes_no(checkout.provider == 'stripe' and not checkout.simulated)}")
    print()

    print("Farmer onboarding (Stripe Connect Express)")
    print("------------------------------------------")
    onboarding = onboard_stripe_express_account(
        farm_name="Preview Farm",
        refresh_url="https://example.com/agribroker/stripe/refresh",
        return_url="https://example.com/agribroker/stripe/return",
    )
    print(f"Provider: {onboarding.provider}")
    print(f"Status: {onboarding.status}")
    print(f"Account id: {onboarding.account_id}")
    if onboarding.onboarding_url:
        print(f"Onboarding URL: {onboarding.onboarding_url}")
    if onboarding.reason:
        print(f"Reason: {onboarding.reason}")
    print(f"Live onboarding ready: {_yes_no(not onboarding.simulated)}")
    print()

    print("Farm payouts (Stripe Connect transfers)")
    print("---------------------------------------")
    payout = create_stripe_connect_transfer(
        order_id="order-preview",
        recipient_account_id="acct_demo_farm_a",
        amount=86.0,
    )
    print(f"Simulated: {_yes_no(payout.simulated)}")
    print(f"Status: {payout.status}")
    print(f"Reference (tx_hash): {payout.tx_hash}")
    if payout.reason:
        print(f"Reason: {payout.reason}")
    print(f"Live Connect transfers ready: {_yes_no(not payout.simulated)}")
    print()

    print("Demo connected account ids (config/farms.json)")
    print("----------------------------------------------")
    for name, account_id in _demo_account_ids():
        print(f"{name}: {account_id}")
    print()

    print("Notes")
    print("-----")
    print("- Buyer Checkout needs only STRIPE_SECRET_KEY.")
    print("- Connect onboarding needs STRIPE_SECRET_KEY *and* STRIPE_CONNECT_ONBOARDING_ENABLED=true.")
    print("- Connect transfers need STRIPE_SECRET_KEY *and* STRIPE_CONNECT_TRANSFERS_ENABLED=true.")
    print("- The acct_demo_* ids above are placeholders. Real Connect payouts require")
    print("  genuinely onboarded Stripe connected accounts (created via Stripe Connect")
    print("  onboarding), not demo strings. Until then farm payouts stay simulated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
