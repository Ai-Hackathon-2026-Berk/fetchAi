from agents.asi_chat_agent import (
    agentverse_readme_path,
    build_failure_response,
    build_text_chat_message,
    chat_progress_enabled,
    extract_text_from_chat_message,
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


def test_chat_progress_enabled_defaults_to_true(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_CHAT_PROGRESS", raising=False)

    assert chat_progress_enabled() is True


def test_chat_progress_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGRIBROKER_CHAT_PROGRESS", "false")

    assert chat_progress_enabled() is False


def test_build_text_chat_message_can_end_session() -> None:
    message = build_text_chat_message("Receipt ready.", end_session=True)

    assert message.content[0].text == "Receipt ready."
    assert message.content[-1].type == "end-session"


def test_agentverse_readme_path_exists() -> None:
    assert agentverse_readme_path() == "docs/agentverse-profile.md"
