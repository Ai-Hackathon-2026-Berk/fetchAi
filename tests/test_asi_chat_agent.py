from types import SimpleNamespace

from agents.asi_chat_agent import (
    agentverse_readme_path,
    build_failure_response,
    build_reasoning_messages,
    build_text_chat_message,
    chat_progress_enabled,
    extract_confirmation_order_id,
    extract_text_from_chat_message,
    fallback_business_quote,
    send_progress_messages,
)


def _fake_run(
    *,
    status: str,
    qty: int = 500,
    quotes: list[SimpleNamespace] | None = None,
    allocations: list[SimpleNamespace] | None = None,
    settlements: list[object] | None = None,
    allocated_qty: int = 500,
    shortfall: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        intent=SimpleNamespace(item="tomatoes", qty=qty),
        quotes=quotes or [],
        split=SimpleNamespace(
            allocations=allocations or [],
            allocated_qty=allocated_qty,
            shortfall=shortfall,
        ),
        settlements=settlements or [],
        status=status,
    )


class FakeTextContent:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeMessage:
    def __init__(self, *items: object) -> None:
        self.content = list(items)


def test_extract_text_from_chat_message() -> None:
    msg = FakeMessage(FakeTextContent("I need 500"), FakeTextContent("tomatoes under 250 FET."))

    assert extract_text_from_chat_message(msg) == "I need 500 tomatoes under 250 FET."


def test_failure_response_guides_user() -> None:
    response = build_failure_response(ValueError("missing quantity"))

    assert "AgriBroker could not complete" in response
    assert "I need 500 tomatoes under $250" in response


def test_chat_progress_enabled_defaults_to_false(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_CHAT_PROGRESS", raising=False)

    assert chat_progress_enabled() is False


def test_chat_progress_can_be_enabled(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_CHAT_PROGRESS", "true")

    assert chat_progress_enabled() is True


def test_chat_progress_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_CHAT_PROGRESS", "false")

    assert chat_progress_enabled() is False


def test_legacy_progress_helper_exists() -> None:
    assert callable(send_progress_messages)


def test_build_text_chat_message_can_end_session() -> None:
    message = build_text_chat_message("Receipt ready.", end_session=True)

    assert message.content[0].text == "Receipt ready."
    assert message.content[-1].type == "end-session"


def test_agentverse_readme_path_exists() -> None:
    assert agentverse_readme_path() == "docs/agentverse-profile.md"


def test_extract_confirmation_order_id() -> None:
    assert extract_confirmation_order_id("confirm order order-abc12345") == "order-abc12345"
    assert extract_confirmation_order_id("confirm order") == ""
    assert extract_confirmation_order_id("confrim order") == ""
    assert extract_confirmation_order_id("I paid") == ""
    assert extract_confirmation_order_id("I need tomatoes") is None


def test_build_reasoning_messages_confirmed_flow() -> None:
    run = _fake_run(
        status="confirmed",
        quotes=[
            SimpleNamespace(seller="Farm A", qty_available=200, unit_price=0.4),
            SimpleNamespace(seller="Green Valley", qty_available=300, unit_price=0.42),
        ],
        allocations=[
            SimpleNamespace(seller="Farm A", qty=200),
            SimpleNamespace(seller="Green Valley", qty=300),
        ],
        settlements=[object(), object()],
    )

    messages = build_reasoning_messages(run)

    assert messages[0] == "🔎 Found 2 seller(s) offering tomatoes."
    assert any("Quotes:" in m and "Farm A 200@0.40" in m for m in messages)
    assert any("Optimal split: 200×Farm A + 300×Green Valley" in m for m in messages)
    assert messages[-1] == "💸 Settling 2 farm payout(s)…"


def test_build_reasoning_messages_shortfall_and_over_budget() -> None:
    partial = _fake_run(status="partial", allocated_qty=300, shortfall=200, settlements=[])
    assert any("short 200" in m for m in build_reasoning_messages(partial))

    over = _fake_run(status="over_budget", settlements=[])
    assert any("exceeds your budget" in m for m in build_reasoning_messages(over))


def test_build_reasoning_messages_payment_pending() -> None:
    run = _fake_run(status="payment_pending", settlements=[])
    assert any("Stripe Checkout" in m for m in build_reasoning_messages(run))


def test_fallback_business_quote_uses_sunny_acres_catalog(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_BUSINESS_SELLER_NAME", "Sunny Acres")

    quote = fallback_business_quote("I need 500 tomatoes under $250.")

    assert quote is not None
    assert quote.seller == "Sunny Acres"
    assert quote.qty_available == 300
    assert quote.unit_price == 0.48
