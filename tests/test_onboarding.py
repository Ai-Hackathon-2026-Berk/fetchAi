import json
import sys
import types

import pytest

from agents.onboarding import (
    OnboardingError,
    add_farm_to_config,
    build_farm_entry,
    existing_ports_from_config,
    generate_seed,
    next_available_port,
    onboard_farmer,
    onboard_stripe_express_account,
    slugify,
)
from agents.workflow import load_farms
from scripts.validate_config import load_config, validate_config


def _base_config() -> dict:
    return {
        "demo_item": "tomatoes",
        "buyer_prompt": "I need 500 tomatoes under $250.",
        "farms": [
            {
                "name": "Farm A",
                "seed": "seed-a",
                "port": 8101,
                "personality": "low-cost",
                "stripe_connected_account_id": "acct_demo_farm_a",
                "catalog": {
                    "tomatoes": {"stock": 200, "base_unit_price": 0.4, "price_floor": 0.36}
                },
            },
            {
                "name": "Farm B",
                "seed": "seed-b",
                "port": 8102,
                "personality": "mid-size",
                "stripe_connected_account_id": "acct_demo_farm_b",
                "catalog": {
                    "tomatoes": {"stock": 400, "base_unit_price": 0.45, "price_floor": 0.41}
                },
            },
        ],
    }


def _write_config(tmp_path, payload: dict | None = None):
    path = tmp_path / "farms.json"
    path.write_text(json.dumps(payload or _base_config(), indent=2) + "\n")
    return path


def _fake_stripe(monkeypatch: pytest.MonkeyPatch, *, raises: Exception | None = None) -> dict:
    created: dict[str, object] = {}

    class FakeAccount:
        id = "acct_real_green_valley"

    class FakeAccountLink:
        url = "https://connect.stripe.test/onboarding"

    class FakeAccountAPI:
        @staticmethod
        def create(**kwargs: object) -> FakeAccount:
            created["account"] = kwargs
            if raises is not None:
                raise raises
            return FakeAccount()

    class FakeAccountLinkAPI:
        @staticmethod
        def create(**kwargs: object) -> FakeAccountLink:
            created["account_link"] = kwargs
            return FakeAccountLink()

    fake_stripe = types.SimpleNamespace(
        api_key=None,
        Account=FakeAccountAPI,
        AccountLink=FakeAccountLinkAPI,
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    return created


def test_slugify() -> None:
    assert slugify("Green Valley Farm!") == "green_valley_farm"
    assert slugify("  ") == "farm"


def test_next_available_port() -> None:
    assert next_available_port([]) == 8101
    assert next_available_port([8101, 8103]) == 8104
    assert next_available_port([7000]) == 8101


def test_generate_seed() -> None:
    assert generate_seed("Green Valley", suffix="abcd1234") == "agri-green_valley-abcd1234-seed"


def test_build_farm_entry_validates_when_added_to_config() -> None:
    farm = build_farm_entry(
        name="Green Valley",
        items=[{"item": "tomatoes", "stock": 300, "base_unit_price": 0.42, "price_floor": 0.38}],
        personality="fresh local tomatoes",
        port=8103,
        seed="seed-green",
        stripe_connected_account_id="acct_demo_green_valley",
    )
    payload = _base_config()
    payload["farms"].append(farm)

    assert validate_config(payload) == []


def test_add_farm_to_config_writes_valid_loadable_config(tmp_path) -> None:
    path = _write_config(tmp_path)
    farm = build_farm_entry(
        name="Green Valley",
        items=[{"item": "tomatoes", "stock": 300, "base_unit_price": 0.42, "price_floor": 0.38}],
        personality="fresh local tomatoes",
        port=8103,
        seed="seed-green",
        stripe_connected_account_id="acct_demo_green_valley",
    )

    add_farm_to_config(farm, config_path=path)

    payload = load_config(path)
    assert validate_config(payload) == []
    assert [farm.name for farm in load_farms(path)][-1] == "Green Valley"


def test_add_farm_to_config_rejects_duplicate_name(tmp_path) -> None:
    path = _write_config(tmp_path)
    farm = build_farm_entry(
        name="Farm A",
        items=[{"item": "tomatoes", "stock": 300, "base_unit_price": 0.42, "price_floor": 0.38}],
        personality="duplicate",
        port=8103,
        seed="seed-duplicate",
        stripe_connected_account_id="acct_demo_duplicate",
    )

    with pytest.raises(OnboardingError, match="farm name already exists"):
        add_farm_to_config(farm, config_path=path)


def test_add_farm_to_config_rejects_duplicate_port(tmp_path) -> None:
    path = _write_config(tmp_path)
    farm = build_farm_entry(
        name="Green Valley",
        items=[{"item": "tomatoes", "stock": 300, "base_unit_price": 0.42, "price_floor": 0.38}],
        personality="duplicate port",
        port=8101,
        seed="seed-green",
        stripe_connected_account_id="acct_demo_green_valley",
    )

    with pytest.raises(OnboardingError, match="farm port already exists"):
        add_farm_to_config(farm, config_path=path)


def test_existing_ports_from_config(tmp_path) -> None:
    path = _write_config(tmp_path)

    assert existing_ports_from_config(path) == [8101, 8102]


def test_stripe_onboarding_simulates_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    result = onboard_stripe_express_account(
        farm_name="Green Valley",
        refresh_url="https://example.test/refresh",
        return_url="https://example.test/return",
    )

    assert result.simulated
    assert result.account_id == "acct_demo_green_valley"
    assert "STRIPE_SECRET_KEY missing" in (result.reason or "")


def test_stripe_onboarding_simulates_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_ONBOARDING_ENABLED", "false")

    result = onboard_stripe_express_account(
        farm_name="Green Valley",
        refresh_url="https://example.test/refresh",
        return_url="https://example.test/return",
    )

    assert result.simulated
    assert "STRIPE_CONNECT_ONBOARDING_ENABLED" in (result.reason or "")


def test_stripe_onboarding_can_create_real_account_with_fake_stripe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _fake_stripe(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_ONBOARDING_ENABLED", "true")

    result = onboard_stripe_express_account(
        farm_name="Green Valley",
        refresh_url="https://example.test/refresh",
        return_url="https://example.test/return",
    )

    assert not result.simulated
    assert result.account_id == "acct_real_green_valley"
    assert result.onboarding_url == "https://connect.stripe.test/onboarding"
    assert created["account"]["type"] == "express"
    assert created["account_link"]["account"] == "acct_real_green_valley"


def test_stripe_onboarding_simulates_on_stripe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_stripe(monkeypatch, raises=RuntimeError("stripe boom"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_ONBOARDING_ENABLED", "true")

    result = onboard_stripe_express_account(
        farm_name="Green Valley",
        refresh_url="https://example.test/refresh",
        return_url="https://example.test/return",
    )

    assert result.simulated
    assert "stripe boom" in (result.reason or "")


def test_onboard_farmer_wires_simulated_stripe_account_into_entry() -> None:
    result = onboard_farmer(
        name="Green Valley",
        items=[{"item": "tomatoes", "stock": 300, "base_unit_price": 0.42, "price_floor": 0.38}],
        personality="fresh local tomatoes",
        existing_ports=[8101, 8102],
        seed_suffix="abcd1234",
        use_stripe=False,
    )
    payload = _base_config()
    payload["farms"].append(result.farm_entry)

    assert result.stripe.simulated
    assert result.farm_entry["stripe_connected_account_id"] == "acct_demo_green_valley"
    assert result.farm_entry["port"] == 8103
    assert validate_config(payload) == []
