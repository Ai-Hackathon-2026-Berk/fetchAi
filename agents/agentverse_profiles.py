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
        "description": (
            "AgriBroker discovery registry — the marketplace phone book. Farm agents "
            "register their catalogs here, and the orchestrator asks it who sells a given item."
        ),
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
        "description": (
            "AgriBroker coordinator — turns one buyer request into a live procurement run: "
            "discovers farms, gathers quotes, optimizes the cheapest split, settles payment, and returns one receipt."
        ),
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
    item_list = ", ".join(items) or "produce"
    personality = state.personality.strip()
    suffix = "" if personality.endswith((".", "!", "?")) else "."
    return {
        "description": (
            f"{state.name} — {personality}{suffix} Sells {item_list} on AgriBroker "
            "with live quotes, invoices, and order receipts."
        ),
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
