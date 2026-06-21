from agents.optimizer import Quote, optimize_split


def test_exact_fill_from_one_seller() -> None:
    result = optimize_split(
        [Quote("Farm A", "tomatoes", qty_available=500, unit_price=0.4)],
        qty_needed=200,
    )

    assert result.fulfilled
    assert result.total_cost == 80.0
    assert result.allocations[0].seller == "Farm A"
    assert result.allocations[0].qty == 200


def test_splits_across_cheapest_sellers() -> None:
    result = optimize_split(
        [
            Quote("Farm C", "tomatoes", qty_available=100, unit_price=0.5),
            Quote("Farm B", "tomatoes", qty_available=400, unit_price=0.45),
            Quote("Farm A", "tomatoes", qty_available=200, unit_price=0.4),
        ],
        qty_needed=500,
        budget=250,
    )

    assert result.fulfilled
    assert not result.over_budget
    assert result.total_cost == 215.0
    assert [(a.seller, a.qty) for a in result.allocations] == [
        ("Farm A", 200),
        ("Farm B", 300),
    ]


def test_tie_prices_are_deterministic_by_seller_name() -> None:
    result = optimize_split(
        [
            Quote("Farm B", "tomatoes", qty_available=100, unit_price=0.4),
            Quote("Farm A", "tomatoes", qty_available=100, unit_price=0.4),
        ],
        qty_needed=150,
    )

    assert [(a.seller, a.qty) for a in result.allocations] == [
        ("Farm A", 100),
        ("Farm B", 50),
    ]


def test_shortfall_returns_partial_plan() -> None:
    result = optimize_split(
        [
            Quote("Farm A", "tomatoes", qty_available=100, unit_price=0.4),
            Quote("Farm B", "tomatoes", qty_available=50, unit_price=0.45),
        ],
        qty_needed=200,
    )

    assert not result.fulfilled
    assert result.allocated_qty == 150
    assert result.shortfall == 50
    assert result.total_cost == 62.5


def test_over_budget_marks_result_without_discarding_plan() -> None:
    result = optimize_split(
        [Quote("Farm A", "tomatoes", qty_available=500, unit_price=0.5)],
        qty_needed=500,
        budget=200,
    )

    assert result.fulfilled
    assert result.over_budget
    assert result.total_cost == 250.0


def test_invalid_quantity_raises() -> None:
    try:
        optimize_split([], qty_needed=0)
    except ValueError as exc:
        assert "qty_needed" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

