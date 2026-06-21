from agents.asi_chat_agent import build_failure_response, extract_text_from_chat_message


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
    assert "I need 500 tomatoes under 250 FET" in response
