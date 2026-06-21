from __future__ import annotations

import argparse
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

from agents.onboarding import (
    DEFAULT_CONFIG_PATH,
    OnboardingError,
    add_farm_to_config,
    existing_ports_from_config,
    onboard_farmer,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Onboard a new AgriBroker farmer.")
    parser.add_argument("--name", help="Farm name")
    parser.add_argument("--item", help="Catalog item, e.g. tomatoes")
    parser.add_argument("--stock", type=int, help="Available stock for the item")
    parser.add_argument("--price", type=float, help="Base unit price")
    parser.add_argument("--floor", type=float, help="Lowest acceptable unit price")
    parser.add_argument("--personality", default="", help="Short seller personality/positioning")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Config path to update")
    parser.add_argument("--dry-run", action="store_true", help="Print the new farm without writing config")
    parser.add_argument("--stripe", action="store_true", help="Try gated Stripe Express onboarding")
    parser.add_argument("--no-stripe", action="store_true", help="Use simulated Stripe onboarding")
    args = parser.parse_args(argv)

    try:
        scripted = _has_scripted_catalog_args(args)
        default_personality = "new self-onboarded AgriBroker seller"
        name = args.name or _prompt_required("Farm name")
        item = args.item or _prompt_required("Item", default="tomatoes")
        stock = args.stock if args.stock is not None else _prompt_int("Stock")
        price = args.price if args.price is not None else _prompt_float("Base unit price")
        floor = args.floor if args.floor is not None else _prompt_float("Price floor")
        if args.personality:
            personality = args.personality
        elif scripted:
            personality = default_personality
        else:
            personality = _prompt_optional("Personality", default=default_personality)
        use_stripe = args.stripe and not args.no_stripe

        result = onboard_farmer(
            name=name,
            items=[
                {
                    "item": item,
                    "stock": stock,
                    "base_unit_price": price,
                    "price_floor": floor,
                }
            ],
            personality=personality,
            existing_ports=existing_ports_from_config(args.config),
            seed_suffix=uuid4().hex[:8],
            use_stripe=use_stripe,
        )

        if not args.dry_run:
            add_farm_to_config(result.farm_entry, config_path=args.config)

        _print_summary(result.farm_entry, result.stripe, args.config, wrote=not args.dry_run)
        return 0
    except (OnboardingError, ValueError) as exc:
        print(f"Onboarding failed: {exc}", file=sys.stderr)
        return 1


def _prompt_required(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default


def _has_scripted_catalog_args(args: argparse.Namespace) -> bool:
    return all(
        value is not None
        for value in (args.name, args.item, args.stock, args.price, args.floor)
    )


def _prompt_optional(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def _prompt_int(label: str) -> int:
    while True:
        try:
            return int(_prompt_required(label))
        except ValueError:
            print("Please enter a whole number.")


def _prompt_float(label: str) -> float:
    while True:
        try:
            return float(_prompt_required(label))
        except ValueError:
            print("Please enter a number.")


def _print_summary(farm_entry: dict, stripe: object, config_path: Path, *, wrote: bool) -> None:
    farm_name = farm_entry["name"]
    print()
    print("Farmer onboarded")
    print("----------------")
    print(f"Name: {farm_name}")
    print(f"Port: {farm_entry['port']}")
    print(f"Stripe account: {stripe.account_id}")
    print(f"Stripe status: {stripe.status}")
    if stripe.onboarding_url:
        print(f"Stripe onboarding URL: {stripe.onboarding_url}")
    if stripe.reason:
        print(f"Reason: {stripe.reason}")
    print(f"Config: {'updated' if wrote else 'dry run only'} ({config_path})")
    print()
    print("Go-live command:")
    print(f'python -m agents.farmer_agent --name "{farm_name}" --registry <REGISTRY_ADDRESS>')


if __name__ == "__main__":
    raise SystemExit(main())
