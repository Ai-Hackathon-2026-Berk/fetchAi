import asyncio

from agents.optimizer import Quote
from agents.payments import BuyerFundingResult
from agents.workflow import format_procurement_response, load_farms, run_procurement_locally
from agents.workflow import run_business_procurement, run_procurement


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
    assert "Stripe steps:" in response
    assert "- Checkout Session simulated: cs_simulated_" in response
    assert "- Connect transfer simulated: tr_simulated_" in response
    assert "to Farm A Stripe account for $80.00" in response
    assert "to Green Valley Stripe account for $126.00" in response
    assert "Order confirmed. Your 500 tomatoes order has been placed" in response


def test_farms_load_stripe_connected_account_ids() -> None:
    farms = load_farms()

    assert farms[0].stripe_connected_account_id == "acct_demo_farm_a"


def test_business_quote_overlays_sunny_acres_and_wins(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    # Sunny Acres' Business Agent undercuts everyone at 0.30/unit for 300 units.
    live = Quote(seller="Sunny Acres", item="tomatoes", qty_available=300, unit_price=0.30)
    run = run_procurement_locally(
        "I need 500 tomatoes under 250 FET.",
        payment_mode="simulated",
        business_quote=live,
    )

    # The live quote should be used and Sunny Acres should win an allocation.
    sunny = next(q for q in run.quotes if q.seller == "Sunny Acres")
    assert sunny.unit_price == 0.30
    sellers = [s.allocation.seller for s in run.settlements]
    assert "Sunny Acres" in sellers
    assert run.status == "confirmed"


def test_business_quote_for_unknown_seller_is_ignored(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    bogus = Quote(seller="Nonexistent Farm", item="tomatoes", qty_available=999, unit_price=0.01)
    run = run_procurement_locally(
        "I need 500 tomatoes under 250 FET.",
        payment_mode="simulated",
        business_quote=bogus,
    )
    # Unknown seller must not enter the quote set (settlement safety).
    assert all(q.seller != "Nonexistent Farm" for q in run.quotes)


def test_business_quote_quantity_clamped_to_stock(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    # Claims more stock than Sunny Acres actually has (config stock is 300).
    greedy = Quote(seller="Sunny Acres", item="tomatoes", qty_available=99999, unit_price=0.10)
    run = run_procurement_locally(
        "I need 500 tomatoes under 250 FET.",
        payment_mode="simulated",
        business_quote=greedy,
    )
    sunny = next(q for q in run.quotes if q.seller == "Sunny Acres")
    assert sunny.qty_available <= 300  # clamped to real stock, fulfillment is safe


def test_business_only_procurement_uses_only_business_agent(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    quote = Quote(seller="Sunny Acres", item="tomatoes", qty_available=300, unit_price=0.48)

    run = asyncio.run(
        run_business_procurement(
            "I need 250 tomatoes under $150.",
            business_quote=quote,
            payment_mode="stripe_connect",
            intent_mode="local",
        )
    )
    response = format_procurement_response(run)

    assert run.status == "confirmed"
    assert [q.seller for q in run.quotes] == ["Sunny Acres"]
    assert run.split.total_cost == 120.0
    assert run.settlements[0].payment.status == "business_agent_confirmed"
    assert "- Farm payout mode: Business Agent confirmation" in response
    assert "Agent trace:" in response
    assert "Business Agent quote from Sunny Acres" in response


def test_business_only_shortfall_does_not_pay(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    quote = Quote(seller="Sunny Acres", item="tomatoes", qty_available=300, unit_price=0.48)

    run = asyncio.run(
        run_business_procurement(
            "I need 500 tomatoes under $300.",
            business_quote=quote,
            payment_mode="stripe_connect",
            intent_mode="local",
        )
    )

    assert run.status == "partial"
    assert run.split.shortfall == 200
    assert run.settlements == ()


def test_real_checkout_link_defers_farm_payouts(monkeypatch, tmp_path) -> None:
    farms = load_farms()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    funding = BuyerFundingResult(
        order_id="order-test",
        amount=206.0,
        currency="usd",
        status="unpaid",
        provider="stripe",
        reference="cs_test_demo",
        checkout_url="https://checkout.stripe.test/session",
        simulated=False,
    )

    run = asyncio.run(
        run_procurement(
            "I need 500 tomatoes under $250.",
            farms=farms,
            payment_mode="stripe_connect",
            intent_mode="local",
            buyer_funding_override=funding,
        )
    )
    response = format_procurement_response(run)

    assert run.status == "payment_pending"
    assert run.settlements == ()
    assert "- Status: payment_pending" in response
    assert "[Open Stripe Checkout](https://checkout.stripe.test/session)" in response
    assert "Farm payouts: waiting for Stripe payment confirmation" in response
    assert "Order confirmed." not in response
    assert "confirm order" in response


def test_paid_stripe_confirmation_returns_final_receipt(monkeypatch, tmp_path) -> None:
    farms = load_farms()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "false")
    funding = BuyerFundingResult(
        order_id="order-paid",
        amount=206.0,
        currency="usd",
        status="paid",
        provider="stripe",
        reference="cs_test_paid_123456789",
        checkout_url=None,
        simulated=False,
    )

    run = asyncio.run(
        run_procurement(
            "I need 500 tomatoes under $250.",
            farms=farms,
            payment_mode="stripe_connect",
            intent_mode="local",
            buyer_funding_override=funding,
        )
    )
    response = format_procurement_response(run)

    assert run.status == "confirmed"
    assert response.startswith("Payment confirmed for order order-paid.")
    assert "Final receipt:" in response
    assert "Quotes:" not in response
    assert "Optimal split:" not in response
    assert "- Buyer payment: Stripe Checkout paid (cs_test_paid_1...456789)" in response
    assert "- Checkout Session confirmed: Stripe Checkout paid (cs_test_paid_1...456789)" in response
    assert "[Open Stripe Checkout]" not in response
    assert "None" not in response
    assert "Order confirmed. Your 500 tomatoes order has been placed" in response


def test_quotes_show_available_inventory_and_stable_prices(monkeypatch) -> None:
    monkeypatch.delenv("AGRIBROKER_BUYER_PAYMENT_MODE", raising=False)
    monkeypatch.delenv("AGRIBROKER_DYNAMIC_PRICING", raising=False)

    run = run_procurement_locally("I need 100 tomatoes under $150.", payment_mode="simulated")
    response = format_procurement_response(run)

    assert "- Farm A: 200 @ 0.40 FET" in response
    assert "- Farm B: 400 @ 0.45 FET" in response
    assert "- Green Valley: 300 @ 0.42 FET" in response


def test_shared_farm_state_depletes_inventory_after_confirmed_order(monkeypatch, tmp_path) -> None:
    farms = load_farms()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "false")
    funding = BuyerFundingResult(
        order_id="order-paid",
        amount=206.0,
        currency="usd",
        status="paid",
        provider="stripe",
        reference="cs_test_paid_123456789",
        checkout_url=None,
        simulated=False,
    )

    first_run = asyncio.run(
        run_procurement(
            "I need 500 tomatoes under $250.",
            farms=farms,
            payment_mode="stripe_connect",
            intent_mode="local",
            buyer_funding_override=funding,
        )
    )
    second_run = asyncio.run(
        run_procurement(
            "I need 400 tomatoes under $150.",
            farms=farms,
            payment_mode="stripe_connect",
            intent_mode="local",
        )
    )
    response = format_procurement_response(second_run)

    assert first_run.status == "confirmed"
    assert {quote.seller for quote in second_run.quotes} == {"Farm B", "Farm C", "Sunny Acres"}
    assert "- Farm A:" not in response
    assert "- Green Valley:" not in response
    assert "- Farm B: 400 @ $0.45" in response
