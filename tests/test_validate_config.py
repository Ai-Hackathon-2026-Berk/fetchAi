"""Unit tests for the farms config validator.

Each rule is driven through the pure ``validate_config`` function with an
in-memory payload, so the tests never depend on (or mutate) config/farms.json.
A single sanity test loads the real config to guard against drift.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from scripts.validate_config import load_config, validate_config

ROOT = Path(__file__).resolve().parents[1]


def _valid_config() -> dict[str, Any]:
    return {
        "demo_item": "tomatoes",
        "buyer_prompt": "I need 500 tomatoes under $250.",
        "farms": [
            {
                "name": "Farm A",
                "seed": "seed-a",
                "port": 8101,
                "personality": "low-cost",
                "catalog": {
                    "tomatoes": {"stock": 200, "base_unit_price": 0.4, "price_floor": 0.36}
                },
            },
            {
                "name": "Farm B",
                "seed": "seed-b",
                "port": 8102,
                "personality": "mid-size",
                "catalog": {
                    "tomatoes": {"stock": 400, "base_unit_price": 0.45, "price_floor": 0.41}
                },
            },
        ],
    }


def test_valid_config_has_no_errors() -> None:
    assert validate_config(_valid_config()) == []


def test_real_config_file_is_valid() -> None:
    payload = load_config(ROOT / "config" / "farms.json")
    assert validate_config(payload) == []


def test_root_must_be_object() -> None:
    assert validate_config(["not", "a", "dict"]) == ["config root must be a JSON object"]


def test_missing_buyer_prompt() -> None:
    config = _valid_config()
    del config["buyer_prompt"]
    assert "missing or empty 'buyer_prompt'" in validate_config(config)


def test_empty_buyer_prompt() -> None:
    config = _valid_config()
    config["buyer_prompt"] = "   "
    assert "missing or empty 'buyer_prompt'" in validate_config(config)


def test_missing_demo_item() -> None:
    config = _valid_config()
    del config["demo_item"]
    assert "missing or empty 'demo_item'" in validate_config(config)


def test_farms_must_be_nonempty_list() -> None:
    config = _valid_config()
    config["farms"] = []
    assert "'farms' must be a non-empty list" in validate_config(config)


def test_missing_required_farm_field() -> None:
    for field in ("name", "seed", "port", "personality", "catalog"):
        config = _valid_config()
        del config["farms"][0][field]
        errors = validate_config(config)
        assert any(f"missing required field '{field}'" in error for error in errors), field


def test_duplicate_farm_names() -> None:
    config = _valid_config()
    config["farms"][1]["name"] = "Farm A"
    assert "duplicate farm name: 'Farm A'" in validate_config(config)


def test_duplicate_ports() -> None:
    config = _valid_config()
    config["farms"][1]["port"] = 8101
    assert "duplicate port: 8101" in validate_config(config)


def test_port_must_be_integer() -> None:
    config = _valid_config()
    config["farms"][0]["port"] = "8101"
    assert any("'port' must be an integer" in error for error in validate_config(config))


def test_port_true_is_rejected_as_bool() -> None:
    config = _valid_config()
    config["farms"][0]["port"] = True
    assert any("'port' must be an integer" in error for error in validate_config(config))


def test_missing_catalog_item_field() -> None:
    for field in ("stock", "base_unit_price", "price_floor"):
        config = _valid_config()
        del config["farms"][0]["catalog"]["tomatoes"][field]
        errors = validate_config(config)
        assert any(f"missing '{field}'" in error for error in errors), field


def test_catalog_must_be_nonempty() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"] = {}
    assert any("'catalog' must be a non-empty object" in error for error in validate_config(config))


def test_negative_stock_rejected() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"]["tomatoes"]["stock"] = -5
    assert any("stock must be a non-negative integer" in error for error in validate_config(config))


def test_zero_stock_allowed() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"]["tomatoes"]["stock"] = 0
    assert validate_config(config) == []


def test_float_stock_rejected() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"]["tomatoes"]["stock"] = 10.5
    assert any("stock must be a non-negative integer" in error for error in validate_config(config))


def test_nonpositive_base_price_rejected() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"]["tomatoes"]["base_unit_price"] = 0
    assert any(
        "base_unit_price must be a positive number" in error
        for error in validate_config(config)
    )


def test_negative_price_floor_rejected() -> None:
    config = _valid_config()
    config["farms"][0]["catalog"]["tomatoes"]["price_floor"] = -1
    assert any(
        "price_floor must be a positive number" in error
        for error in validate_config(config)
    )


def test_price_floor_above_base_price_rejected() -> None:
    config = _valid_config()
    item = config["farms"][0]["catalog"]["tomatoes"]
    item["price_floor"] = 0.9
    item["base_unit_price"] = 0.4
    assert any("exceeds base_unit_price" in error for error in validate_config(config))


def test_price_floor_equal_to_base_price_allowed() -> None:
    config = _valid_config()
    item = config["farms"][0]["catalog"]["tomatoes"]
    item["price_floor"] = 0.4
    item["base_unit_price"] = 0.4
    assert validate_config(config) == []


def test_demo_item_must_appear_in_two_farms() -> None:
    config = _valid_config()
    config["farms"][1]["catalog"] = {
        "peppers": {"stock": 100, "base_unit_price": 0.5, "price_floor": 0.45}
    }
    errors = validate_config(config)
    assert any("must appear in at least 2 farms" in error for error in errors)


def test_demo_item_match_is_case_insensitive() -> None:
    config = _valid_config()
    config["demo_item"] = "Tomatoes"
    config["farms"][0]["catalog"] = {
        "TOMATOES": {"stock": 200, "base_unit_price": 0.4, "price_floor": 0.36}
    }
    assert validate_config(config) == []


def test_multiple_errors_are_all_reported() -> None:
    config = _valid_config()
    del config["buyer_prompt"]
    config["farms"][1]["port"] = 8101
    config["farms"][0]["catalog"]["tomatoes"]["price_floor"] = 9.0
    errors = validate_config(config)
    assert "missing or empty 'buyer_prompt'" in errors
    assert "duplicate port: 8101" in errors
    assert any("exceeds base_unit_price" in error for error in errors)


def test_validate_config_does_not_mutate_input() -> None:
    config = _valid_config()
    snapshot = copy.deepcopy(config)
    validate_config(config)
    assert config == snapshot
