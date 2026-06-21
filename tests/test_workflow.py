from agents.workflow import format_procurement_response, load_farms, run_procurement_locally


def test_local_procurement_demo_flow(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    run = run_procurement_locally("I need 500 tomatoes under 250 FET.", payment_mode="simulated")

    assert run.status == "confirmed"
    assert run.split.total_cost == 206.0
    assert [(s.allocation.seller, s.allocation.qty) for s in run.settlements] == [
        ("Farm A", 200),
        ("Green Valley", 300),
    ]
    assert run.buyer_funding.simulated


def test_chat_response_is_judge_readable(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    run = run_procurement_locally("I need 500 tomatoes under 250 FET.", payment_mode="simulated")
    response = format_procurement_response(run)

    assert "AgriBroker found 5 sellers for tomatoes." in response
    assert "- Farm A: 200 @ 0.40 FET" in response
    assert "- Green Valley: 300 tomatoes = 126.00 FET" in response
    assert "- Total: 206.00 FET" in response
    assert "- Status: confirmed" in response
    assert "- Buyer payment: simulated" in response
    assert "- Farm payout mode: simulated/local demo" in response
    assert "- Buyer funding: simulated-" in response


def test_over_budget_does_not_pay_farms(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    run = run_procurement_locally("I need 500 tomatoes under 100 FET.", payment_mode="simulated")
    response = format_procurement_response(run)

    assert run.status == "over_budget"
    assert run.split.total_cost == 206.0
    assert run.settlements == ()
    assert run.buyer_funding.amount == 0.0
    assert "- Over budget by: 106.00 FET" in response
    assert "- Buyer funding: not requested" in response
    assert "(not paid)" in response


def test_shortfall_does_not_pay_farms(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    run = run_procurement_locally("I need 1500 tomatoes under 1000 FET.", payment_mode="simulated")
    response = format_procurement_response(run)

    assert run.status == "partial"
    assert run.split.shortfall == 200
    assert run.settlements == ()
    assert run.buyer_funding.amount == 0.0
    assert "- Shortfall: 200 tomatoes" in response
    assert "- Buyer funding: not requested" in response
    assert "(not paid)" in response


def test_stripe_connect_procurement_uses_farm_connected_accounts(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    run = run_procurement_locally(
        "I need 500 tomatoes under 250 FET.",
        payment_mode="stripe_connect",
    )
    response = format_procurement_response(run)

    assert [settlement.payment.recipient for settlement in run.settlements] == [
        "acct_demo_farm_a",
        "acct_demo_green_valley",
    ]
    assert all(settlement.payment.simulated for settlement in run.settlements)
    assert "- Farm A: 200 @ $0.40" in response
    assert "- Green Valley: 300 tomatoes = $126.00" in response
    assert "- Total: $206.00" in response
    assert "- Budget: $250.00" in response
    assert "- Buyer payment: Stripe Checkout (simulated)" in response
    assert "- Buyer funding: cs_simulated_" in response
    assert "- Farm payout mode: Stripe Connect (simulated/local demo)" in response


def test_farms_load_stripe_connected_account_ids() -> None:
    farms = load_farms()

    assert farms[0].stripe_connected_account_id == "acct_demo_farm_a"
