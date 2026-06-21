"""Buyer intent parsing.

The ASI:One API adapter is intentionally isolated so local demos can run with the
deterministic parser while the hosted version uses the real API key.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BuyerIntent:
    item: str
    qty: int
    budget: float | None = None
    deadline: str | None = None


def use_mock_intent_parser(value: str | None = None) -> bool | None:
    mode = (value or os.getenv("AGRIBROKER_INTENT_MODE") or "local").strip().lower()
    if mode == "local":
        return True
    if mode == "asi":
        return False
    if mode == "auto":
        return None
    raise ValueError("AGRIBROKER_INTENT_MODE must be 'local', 'asi', or 'auto'")


def parse_buyer_intent(text: str, *, use_mock: bool | None = None) -> BuyerIntent:
    """Parse free text into a procurement intent.

    By default this uses the deterministic parser unless ``ASI_ONE_API_KEY`` is set.
    That keeps the demo reliable and makes tests independent of external services.
    """

    if use_mock is True or not os.getenv("ASI_ONE_API_KEY"):
        return parse_buyer_intent_locally(text)

    try:
        return parse_buyer_intent_with_asi_one(text)
    except Exception:
        return parse_buyer_intent_locally(text)


def parse_buyer_intent_locally(text: str) -> BuyerIntent:
    qty_match = re.search(r"\b(\d{1,7})\b", text)
    if not qty_match:
        raise ValueError("Please include a quantity, for example: 500 tomatoes.")

    qty = int(qty_match.group(1))
    after_qty = text[qty_match.end() :]
    item_match = re.search(r"\b([A-Za-z][A-Za-z -]*)\b", after_qty)
    if not item_match:
        raise ValueError("Please include an item, for example: tomatoes.")

    item = item_match.group(1).strip().lower()
    item = re.sub(r"\b(under|below|for|by|before|within|budget|fet|dollars?)\b.*", "", item).strip()
    if not item:
        raise ValueError("Please include an item, for example: tomatoes.")

    budget = None
    budget_match = re.search(r"(?:under|below|budget|less than)\s*\$?\s*(\d+(?:\.\d+)?)", text, re.I)
    if budget_match:
        budget = float(budget_match.group(1))

    return BuyerIntent(item=item, qty=qty, budget=budget)


def parse_buyer_intent_with_asi_one(text: str) -> BuyerIntent:
    """Call ASI:One with a strict JSON instruction.

    This assumes an OpenAI-compatible chat completion endpoint. Verify the final
    endpoint and model name during Phase 0 before relying on it for the live demo.
    """

    import requests

    api_key = os.environ["ASI_ONE_API_KEY"]
    base_url = os.getenv("ASI_ONE_BASE_URL", "https://api.asi1.ai/v1/chat/completions")
    model = os.getenv("ASI_ONE_MODEL", "asi1-mini")
    response = requests.post(
        base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract procurement intent as strict JSON with keys "
                        "item, qty, budget, deadline. Use null for missing optional values."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        },
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    content = extract_json_content(content)
    payload: dict[str, Any] = json.loads(content)
    return BuyerIntent(
        item=str(payload["item"]).strip().lower(),
        qty=int(payload["qty"]),
        budget=None if payload.get("budget") is None else float(payload["budget"]),
        deadline=payload.get("deadline"),
    )


def extract_json_content(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
        content = re.sub(r"\s*```$", "", content)
    match = re.search(r"\{.*\}", content, flags=re.S)
    return match.group(0) if match else content


def parse_natural_language_quote(text: str, default_item: str, seller: str) -> dict[str, Any]:
    qty_match = re.search(r"\b(\d{1,7})\b", text)
    price_match = re.search(r"(?:\$|FET\s*)?(\d+(?:\.\d+)?)\s*(?:each|per|/)", text, re.I)
    if not qty_match or not price_match:
        raise ValueError(f"Could not parse quote from {seller}: {text}")
    return {
        "seller": seller,
        "item": default_item,
        "qty_available": int(qty_match.group(1)),
        "unit_price": float(price_match.group(1)),
    }
