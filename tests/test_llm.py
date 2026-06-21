from agents.llm import extract_json_content, parse_buyer_intent_locally, use_mock_intent_parser


def test_local_parser_extracts_tomato_order() -> None:
    intent = parse_buyer_intent_locally("I need 500 tomatoes under $250.")

    assert intent.item == "tomatoes"
    assert intent.qty == 500
    assert intent.budget == 250


def test_intent_mode_mapping() -> None:
    assert use_mock_intent_parser("local") is True
    assert use_mock_intent_parser("asi") is False
    assert use_mock_intent_parser("auto") is None


def test_extract_json_content_from_markdown_fence() -> None:
    assert extract_json_content('```json\n{"item":"tomatoes"}\n```') == '{"item":"tomatoes"}'
