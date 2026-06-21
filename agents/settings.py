"""Runtime settings shared by AgriBroker agents."""

from __future__ import annotations

import os
from typing import Literal

FetchNetwork = Literal["mainnet", "testnet"]
DiscoveryMode = Literal["local", "agent"]


def fetch_network() -> FetchNetwork:
    value = os.getenv("FETCH_NETWORK", "testnet").strip().lower()
    if value not in {"mainnet", "testnet"}:
        raise ValueError("FETCH_NETWORK must be 'mainnet' or 'testnet'")
    return value  # type: ignore[return-value]


def discovery_mode(value: str | None = None) -> DiscoveryMode:
    mode = (value or os.getenv("AGRIBROKER_DISCOVERY_MODE") or "local").strip().lower()
    if mode not in {"local", "agent"}:
        raise ValueError("AGRIBROKER_DISCOVERY_MODE must be 'local' or 'agent'")
    return mode  # type: ignore[return-value]


def registry_address(value: str | None = None) -> str | None:
    address = (value or os.getenv("AGRIBROKER_REGISTRY_ADDRESS") or "").strip()
    return address or None
