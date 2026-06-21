from agents.llm import parse_buyer_intent_locally


def test_local_parser_extracts_tomato_order() -> None:
    intent = parse_buyer_intent_locally("I need 500 tomatoes under $250.")

    assert intent.item == "tomatoes"
    assert intent.qty == 500
    assert intent.budget == 250

