"""Agentverse profile metadata for AgriBroker agents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agents.farm_state import FarmState


AGENTVERSE_DOCS_DIR = Path("docs/agentverse")
COMMON_TAGS = ["AgriBroker", "produce", "marketplace", "procurement", "Stripe", "ASI:One"]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "agent"


def readme_path(filename: str) -> str | None:
    path = AGENTVERSE_DOCS_DIR / filename
    return str(path) if path.exists() else None


def registry_profile_kwargs() -> dict[str, Any]:
    return {
        "description": "Seller discovery registry for the AgriBroker produce marketplace.",
        "handle": "agribroker-registry",
        "readme_path": readme_path("registry.md"),
        "metadata": {
            "role": "registry",
            "category": "procurement",
            "tags": [*COMMON_TAGS, "registry", "discovery"],
        },
        "mailbox": True,
        "publish_agent_details": True,
    }


def orchestrator_profile_kwargs() -> dict[str, Any]:
    return {
        "description": "Structured AgriBroker coordinator for procurement requests, quotes, optimization, and receipts.",
        "handle": "agribroker-orchestrator",
        "readme_path": readme_path("orchestrator.md"),
        "metadata": {
            "role": "orchestrator",
            "category": "procurement",
            "tags": [*COMMON_TAGS, "orchestrator", "optimizer"],
        },
        "mailbox": True,
        "publish_agent_details": True,
    }


def farmer_profile_kwargs(state: FarmState) -> dict[str, Any]:
    filename = f"{slugify(state.name)}.md"
    items = sorted(state.catalog.keys())
    return {
        "description": f"{state.name} seller agent for AgriBroker produce quotes and order receipts.",
        "handle": f"agribroker-{slugify(state.name)}",
        "readme_path": readme_path(filename) or readme_path("farmer-template.md"),
        "metadata": {
            "role": "farmer",
            "category": "produce",
            "farm_name": state.name,
            "items": items,
            "stripe_connected_account_id": state.stripe_connected_account_id,
            "tags": [*COMMON_TAGS, "farm", *items],
        },
        "mailbox": True,
        "publish_agent_details": True,
    }
