"""Farmer self-onboarding helpers for AgriBroker."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validate_config import validate_config


DEFAULT_CONFIG_PATH = Path("config/farms.json")
DEFAULT_PORT_START = 8101


class OnboardingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StripeOnboardingResult:
    account_id: str
    onboarding_url: str | None
    status: str
    provider: str
    simulated: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FarmOnboardingResult:
    farm_entry: dict[str, Any]
    stripe: StripeOnboardingResult


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "farm"


def next_available_port(existing_ports: list[int], start: int = DEFAULT_PORT_START) -> int:
    if not existing_ports:
        return start
    return max(max(existing_ports) + 1, start)


def generate_seed(name: str, *, suffix: str) -> str:
    return f"agri-{slugify(name)}-{suffix}-seed"


def build_farm_entry(
    *,
    name: str,
    items: list[dict[str, Any]],
    personality: str,
    port: int,
    seed: str,
    stripe_connected_account_id: str,
) -> dict[str, Any]:
    catalog: dict[str, dict[str, int | float]] = {}
    for item in items:
        item_name = str(item["item"]).strip().lower()
        catalog[item_name] = {
            "stock": int(item["stock"]),
            "base_unit_price": float(item["base_unit_price"]),
            "price_floor": float(item["price_floor"]),
        }

    return {
        "name": name.strip(),
        "seed": seed,
        "port": int(port),
        "personality": personality.strip() or "new self-onboarded AgriBroker seller",
        "stripe_connected_account_id": stripe_connected_account_id,
        "catalog": catalog,
    }


def add_farm_to_config(
    farm_entry: dict[str, Any],
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    payload = _load_config(config_path)
    farms = payload.setdefault("farms", [])
    if not isinstance(farms, list):
        raise OnboardingError("'farms' must be a list")

    _precheck_duplicate_farm(farms, farm_entry)

    next_payload = dict(payload)
    next_payload["farms"] = [*farms, farm_entry]
    errors = validate_config(next_payload)
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise OnboardingError(f"Onboarded farm would make config invalid:\n{formatted}")

    config_path.write_text(json.dumps(next_payload, indent=2) + "\n")


def onboard_farmer(
    *,
    name: str,
    items: list[dict[str, Any]],
    personality: str,
    existing_ports: list[int],
    seed_suffix: str,
    use_stripe: bool = False,
    refresh_url: str = "https://example.com/agribroker/stripe/refresh",
    return_url: str = "https://example.com/agribroker/stripe/return",
) -> FarmOnboardingResult:
    if use_stripe:
        stripe = onboard_stripe_express_account(
            farm_name=name,
            refresh_url=refresh_url,
            return_url=return_url,
        )
    else:
        stripe = simulated_stripe_onboarding(
            farm_name=name,
            reason="Stripe onboarding skipped; simulated connected account",
        )

    farm_entry = build_farm_entry(
        name=name,
        items=items,
        personality=personality,
        port=next_available_port(existing_ports),
        seed=generate_seed(name, suffix=seed_suffix),
        stripe_connected_account_id=stripe.account_id,
    )
    return FarmOnboardingResult(farm_entry=farm_entry, stripe=stripe)


def onboard_stripe_express_account(
    *,
    farm_name: str,
    refresh_url: str,
    return_url: str,
) -> StripeOnboardingResult:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        return simulated_stripe_onboarding(
            farm_name=farm_name,
            reason="STRIPE_SECRET_KEY missing; simulated Stripe onboarding",
        )

    if not _stripe_connect_onboarding_enabled():
        return simulated_stripe_onboarding(
            farm_name=farm_name,
            reason="STRIPE_CONNECT_ONBOARDING_ENABLED is not 'true'; simulated Stripe onboarding",
        )

    try:
        import stripe

        stripe.api_key = secret_key
        account = stripe.Account.create(
            type="express",
            business_profile={"name": farm_name},
            metadata={"farm_name": farm_name, "source": "agribroker_onboarding"},
        )
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return StripeOnboardingResult(
            account_id=str(account.id),
            onboarding_url=str(account_link.url),
            status="onboarding_created",
            provider="stripe",
            simulated=False,
        )
    except Exception as exc:
        return simulated_stripe_onboarding(
            farm_name=farm_name,
            reason=f"Stripe onboarding failed; simulated: {exc}",
        )


def simulated_stripe_onboarding(farm_name: str, reason: str) -> StripeOnboardingResult:
    return StripeOnboardingResult(
        account_id=f"acct_demo_{slugify(farm_name)}",
        onboarding_url=None,
        status="simulated_created",
        provider="simulated",
        simulated=True,
        reason=reason,
    )


def existing_ports_from_config(config_path: Path = DEFAULT_CONFIG_PATH) -> list[int]:
    payload = _load_config(config_path)
    farms = payload.get("farms", [])
    if not isinstance(farms, list):
        return []
    return [int(farm["port"]) for farm in farms if isinstance(farm, dict) and "port" in farm]


def _stripe_connect_onboarding_enabled() -> bool:
    return os.getenv("STRIPE_CONNECT_ONBOARDING_ENABLED", "").strip().lower() == "true"


def _load_config(config_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(config_path.read_text())
    except FileNotFoundError as exc:
        raise OnboardingError(f"config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise OnboardingError(f"config is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise OnboardingError("config root must be a JSON object")
    return payload


def _precheck_duplicate_farm(farms: list[Any], farm_entry: dict[str, Any]) -> None:
    new_name = str(farm_entry.get("name", "")).strip().lower()
    new_port = farm_entry.get("port")
    for farm in farms:
        if not isinstance(farm, dict):
            continue
        existing_name = str(farm.get("name", "")).strip().lower()
        if new_name and existing_name == new_name:
            raise OnboardingError(f"farm name already exists: {farm_entry.get('name')!r}")
        if new_port == farm.get("port"):
            raise OnboardingError(f"farm port already exists: {new_port}")
