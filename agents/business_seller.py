"""Live quote integration with the Sunny Acres Flockx Business Agent.

AgriBroker contacts a real Fetch.ai Business Agent over the Chat Protocol, asks for
a price in natural language, and turns the reply into a structured ``Quote`` that the
optimizer can use. Everything here is pure (env + text parsing) so it is unit-testable
without a live uAgents runtime; the actual chat send/receive lives in the chat agent.

The Business Agent quote is overlaid onto the existing "Sunny Acres" farm, so the
optimizer and settlement paths work unchanged, and any failure simply falls back to
the seeded config price.
"""

from __future__ import annotations

import asyncio
import os

from agents.llm import parse_natural_language_quote
from agents.optimizer import Quote

DEFAULT_BUSINESS_SELLER_NAME = "Sunny Acres"

# Chat Protocol has no synchronous request/response: a reply arrives later in the
# agent's ChatMessage handler. We correlate it back to the in-flight quote request
# with a per-sender future the handler resolves.
_pending_replies: dict[str, "asyncio.Future[str]"] = {}


def register_pending_reply(address: str) -> "asyncio.Future[str]":
    future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
    _pending_replies[address] = future
    return future


def resolve_pending_reply(address: str, text: str) -> bool:
    """Called by the chat handler when the Business Agent replies. True if it matched."""
    future = _pending_replies.get(address)
    if future is not None and not future.done():
        future.set_result(text)
        return True
    return False


def is_awaiting_reply(address: str) -> bool:
    future = _pending_replies.get(address)
    return future is not None and not future.done()


def clear_pending_reply(address: str) -> None:
    _pending_replies.pop(address, None)


def business_seller_address(value: str | None = None) -> str | None:
    address = (value or os.getenv("AGRIBROKER_BUSINESS_SELLER_ADDRESS") or "").strip()
    return address or None


def business_seller_name() -> str:
    name = (os.getenv("AGRIBROKER_BUSINESS_SELLER_NAME") or "").strip()
    return name or DEFAULT_BUSINESS_SELLER_NAME


def business_seller_enabled() -> bool:
    """The live path is opt-in: only on when an agent address is configured."""
    return business_seller_address() is not None


def build_quote_request_text(qty: int, item: str) -> str:
    return (
        f"How much for {qty} {item}? "
        "Please reply with your price per unit and how many you can supply."
    )


def quote_from_reply(
    text: str,
    *,
    qty: int,
    item: str,
    seller: str | None = None,
) -> Quote | None:
    """Parse a Business Agent's natural-language reply into a Quote, or None.

    Returns None (caller falls back to the config quote) when the reply cannot be
    parsed or yields a non-positive price/quantity. ``qty_available`` is capped at the
    requested quantity; the workflow further clamps it to the farm's real stock.
    """

    seller = seller or business_seller_name()
    try:
        parsed = parse_natural_language_quote(text, default_item=item, seller=seller)
    except ValueError:
        return None

    qty_available = max(0, min(int(parsed["qty_available"]), qty))
    unit_price = float(parsed["unit_price"])
    if qty_available <= 0 or unit_price <= 0:
        return None

    return Quote(
        seller=seller,
        item=item,
        qty_available=qty_available,
        unit_price=unit_price,
    )
