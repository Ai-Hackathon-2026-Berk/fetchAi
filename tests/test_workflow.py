from agents.workflow import format_procurement_response, run_procurement_locally


def test_local_procurement_demo_flow() -> None:
    run = run_procurement_locally("I need 500 tomatoes under 250 FET.", payment_mode="simulated")

    assert run.status == "confirmed"
    assert run.split.total_cost == 215.0
    assert [(s.allocation.seller, s.allocation.qty) for s in run.settlements] == [
        ("Farm A", 200),
        ("Farm B", 300),
    ]
    assert run.buyer_funding.simulated


def test_chat_response_is_judge_readable() -> None:
    run = run_procurement_locally("I need 500 tomatoes under 250 FET.", payment_mode="simulated")
    response = format_procurement_response(run)

    assert "AgriBroker found 4 sellers for tomatoes." in response
    assert "Farm A: 200 @ 0.40 FET" in response
    assert "Farm B: 300 tomatoes = 135.00 FET" in response
    assert "Total: 215.00 FET" in response
    assert "Status: confirmed" in response
    assert "Payment mode: simulated/local demo" in response


def test_over_budget_does_not_pay_farms() -> None:
    run = run_procurement_locally("I need 500 tomatoes under 100 FET.", payment_mode="simulated")

    assert run.status == "over_budget"
    assert run.split.total_cost == 215.0
    assert run.settlements == ()
    assert run.buyer_funding.amount_fet == 0.0


def test_shortfall_does_not_pay_farms() -> None:
    run = run_procurement_locally("I need 1200 tomatoes under 1000 FET.", payment_mode="simulated")

    assert run.status == "partial"
    assert run.split.shortfall == 200
    assert run.settlements == ()
    assert run.buyer_funding.amount_fet == 0.0
