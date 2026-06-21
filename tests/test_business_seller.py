import asyncio

from agents.business_seller import (
    build_quote_request_text,
    business_seller_address,
    business_seller_enabled,
    business_seller_name,
    clear_pending_reply,
    is_awaiting_reply,
    quote_from_reply,
    register_pending_reply,
    resolve_pending_reply,
)

# A realistic, chatty Business Agent reply (as Sunny Acres actually answered).
SAMPLE_REPLY = (
    "Sunny Acres can supply 300 tomatoes at $0.48 each (total $144.00).\n\n"
    "We have plenty in stock — ready to go when you are! "
    "Would you like to move forward with the order?"
)


def test_business_seller_disabled_without_address(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUSINESS_SELLER_ADDRESS", raising=False)
    assert business_seller_address() is None
    assert business_seller_enabled() is False


def test_business_seller_enabled_with_address(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_BUSINESS_SELLER_ADDRESS", "agent1qexample")
    assert business_seller_address() == "agent1qexample"
    assert business_seller_enabled() is True


def test_business_seller_name_default(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUSINESS_SELLER_NAME", raising=False)
    assert business_seller_name() == "Sunny Acres"


def test_build_quote_request_text_contains_qty_and_item() -> None:
    text = build_quote_request_text(500, "tomatoes")
    assert "500" in text
    assert "tomatoes" in text


def test_quote_from_reply_parses_chatty_business_reply() -> None:
    quote = quote_from_reply(SAMPLE_REPLY, qty=500, item="tomatoes")

    assert quote is not None
    assert quote.seller == "Sunny Acres"
    assert quote.item == "tomatoes"
    assert quote.qty_available == 300
    assert quote.unit_price == 0.48


def test_quote_from_reply_caps_quantity_at_requested() -> None:
    quote = quote_from_reply(
        "We can supply 300 tomatoes at $0.48 each.", qty=200, item="tomatoes"
    )
    assert quote is not None
    assert quote.qty_available == 200


def test_quote_from_reply_returns_none_when_unparseable() -> None:
    assert quote_from_reply("Sorry, we're sold out right now!", qty=500, item="tomatoes") is None


def test_quote_from_reply_uses_configured_seller_name(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_BUSINESS_SELLER_NAME", "Sunny Acres Co-op")
    quote = quote_from_reply("100 tomatoes at $0.50 each", qty=100, item="tomatoes")
    assert quote is not None
    assert quote.seller == "Sunny Acres Co-op"


def test_pending_reply_future_resolves() -> None:
    async def go() -> str:
        future = register_pending_reply("agent1qx")
        assert is_awaiting_reply("agent1qx") is True
        assert resolve_pending_reply("agent1qx", SAMPLE_REPLY) is True
        result = await future
        clear_pending_reply("agent1qx")
        return result

    assert asyncio.run(go()) == SAMPLE_REPLY


def test_resolve_without_pending_returns_false() -> None:
    assert resolve_pending_reply("agent1q-not-waiting", "anything") is False
    assert is_awaiting_reply("agent1q-not-waiting") is False
