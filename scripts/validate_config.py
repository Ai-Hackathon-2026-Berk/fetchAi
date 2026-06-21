"""Validate config/farms.json before running the AgriBroker demo.

The core ``validate_config`` is a pure function: it takes the already-parsed
config payload and returns a list of human-readable error strings (empty means
valid). Keeping it pure makes every rule trivially unit-testable without touching
the real config file. The ``main`` CLI wrapper handles file IO and exit codes so
``scripts/check_demo_ready.py`` or CI can call it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("config/farms.json")

REQUIRED_FARM_FIELDS: tuple[str, ...] = ("name", "seed", "port", "personality", "catalog")
REQUIRED_ITEM_FIELDS: tuple[str, ...] = ("stock", "base_unit_price", "price_floor")
MIN_FARMS_PER_DEMO_ITEM = 2


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_int(value: Any) -> bool:
    # bool is a subclass of int; reject it so True/False can't pose as a port/stock.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_nonneg_int(value: Any) -> bool:
    return _is_int(value) and value >= 0


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _normalize_item(item: str) -> str:
    return item.strip().lower()


def _farm_sells(farm: Any, item: str) -> bool:
    if not isinstance(farm, dict):
        return False
    catalog = farm.get("catalog")
    if not isinstance(catalog, dict):
        return False
    target = _normalize_item(item)
    return any(isinstance(key, str) and _normalize_item(key) == target for key in catalog)


def _validate_item(label: str, item_name: str, entry: Any) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{label}: catalog item '{item_name}' must be an object"]

    errors: list[str] = []
    for field in REQUIRED_ITEM_FIELDS:
        if field not in entry:
            errors.append(f"{label}: catalog item '{item_name}' missing '{field}'")

    stock = entry.get("stock")
    if "stock" in entry and not _is_nonneg_int(stock):
        errors.append(
            f"{label}: catalog item '{item_name}' stock must be a non-negative integer"
        )

    base_price = entry.get("base_unit_price")
    if "base_unit_price" in entry and not _is_positive_number(base_price):
        errors.append(
            f"{label}: catalog item '{item_name}' base_unit_price must be a positive number"
        )

    floor_price = entry.get("price_floor")
    if "price_floor" in entry and not _is_positive_number(floor_price):
        errors.append(
            f"{label}: catalog item '{item_name}' price_floor must be a positive number"
        )

    if (
        _is_positive_number(base_price)
        and _is_positive_number(floor_price)
        and floor_price > base_price
    ):
        errors.append(
            f"{label}: catalog item '{item_name}' price_floor ({floor_price}) "
            f"exceeds base_unit_price ({base_price})"
        )

    return errors


def _validate_farm(farm: Any, index: int) -> list[str]:
    if not isinstance(farm, dict):
        return [f"farm[{index}] must be an object"]

    label = farm["name"] if _is_nonempty_str(farm.get("name")) else f"farm[{index}]"
    errors: list[str] = []

    for field in REQUIRED_FARM_FIELDS:
        if field not in farm:
            errors.append(f"{label}: missing required field '{field}'")

    if "port" in farm and not _is_int(farm.get("port")):
        errors.append(f"{label}: 'port' must be an integer")

    if "catalog" in farm:
        catalog = farm.get("catalog")
        if not isinstance(catalog, dict) or not catalog:
            errors.append(f"{label}: 'catalog' must be a non-empty object")
        else:
            for item_name, entry in catalog.items():
                errors.extend(_validate_item(label, str(item_name), entry))

    return errors


def _duplicates(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_config(payload: Any) -> list[str]:
    """Return a list of validation errors for a parsed farms config (empty == valid)."""

    if not isinstance(payload, dict):
        return ["config root must be a JSON object"]

    errors: list[str] = []

    if not _is_nonempty_str(payload.get("buyer_prompt")):
        errors.append("missing or empty 'buyer_prompt'")

    demo_item = payload.get("demo_item")
    if not _is_nonempty_str(demo_item):
        errors.append("missing or empty 'demo_item'")

    farms = payload.get("farms")
    if not isinstance(farms, list) or not farms:
        errors.append("'farms' must be a non-empty list")
        return errors

    for index, farm in enumerate(farms):
        errors.extend(_validate_farm(farm, index))

    names = [
        farm["name"]
        for farm in farms
        if isinstance(farm, dict) and _is_nonempty_str(farm.get("name"))
    ]
    for name in _duplicates(names):
        errors.append(f"duplicate farm name: {name!r}")

    ports = [
        farm["port"]
        for farm in farms
        if isinstance(farm, dict) and _is_int(farm.get("port"))
    ]
    for port in _duplicates(ports):
        errors.append(f"duplicate port: {port}")

    if _is_nonempty_str(demo_item):
        sellers = sum(1 for farm in farms if _farm_sells(farm, demo_item))
        if sellers < MIN_FARMS_PER_DEMO_ITEM:
            errors.append(
                f"demo_item {demo_item!r} must appear in at least "
                f"{MIN_FARMS_PER_DEMO_ITEM} farms (found {sellers})"
            )

    return errors


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Any:
    return json.loads(Path(config_path).read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the AgriBroker farms config.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the farms config JSON (default: config/farms.json).",
    )
    args = parser.parse_args(argv)

    try:
        payload = load_config(args.config)
    except FileNotFoundError:
        print(f"config not found: {args.config}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"config is not valid JSON: {exc}")
        return 1

    errors = validate_config(payload)
    if errors:
        print(f"{args.config} is INVALID ({len(errors)} issue(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"{args.config} is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
