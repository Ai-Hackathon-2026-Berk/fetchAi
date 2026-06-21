import asyncio

from agents.agent_network import confirm_pending_order_via_agents, run_procurement_via_agents
from agents.payments import BuyerFundingResult
from agents.protocols import Invoice, PaymentSent, QuoteRequest, QuoteResponse, Receipt, SellerList, WhoSells
from agents.workflow import format_procurement_response


class FakeContext:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []
        self.ledger = None

    async def send_and_receive(
        self,
        destination: str,
        message: object,
        response_type: type[object],
        sync: bool = False,
        timeout: int = 30,
    ) -> tuple[object | None, object | None]:
        self.sent.append((destination, message))

        if isinstance(message, WhoSells):
            return SellerList(item=message.item, addresses=["agent-farm-a", "agent-farm-b"]), None

        if isinstance(message, QuoteRequest) and destination == "agent-farm-a":
            return (
                QuoteResponse(
                    request_id=message.request_id,
                    farmer="Farm A",
                    item=message.item,
                    qty_available=200,
                    unit_price=0.4,
                ),
                None,
            )

        if isinstance(message, QuoteRequest) and destination == "agent-farm-b":
            return (
                QuoteResponse(
                    request_id=message.request_id,
                    farmer="Farm B",
                    item=message.item,
                    qty_available=400,
                    unit_price=0.45,
                ),
                None,
            )

        if destination in {"agent-farm-a", "agent-farm-b"} and message.__class__.__name__ == "PurchaseOrder":
            suffix = "farm_a" if destination == "agent-farm-a" else "farm_b"
            return (
                Invoice(
                    order_id=message.order_id,
                    pay_to_address=f"wallet-{destination}",
                    total_fet=message.qty * message.agreed_unit_price,
                    stripe_connected_account_id=f"acct_demo_{suffix}",
                ),
                None,
            )

        if isinstance(message, PaymentSent):
            return (
                Receipt(
                    order_id=message.order_id,
                    status="confirmed",
                    message=f"{destination} confirmed payment",
                ),
                None,
            )

        return None, None


def test_agent_network_procurement_happy_path() -> None:
    ctx = FakeContext()
    run = asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="simulated",
            intent_mode="local",
            wallet=object(),
        )
    )

    assert run.status == "confirmed"
    assert run.split.total_cost == 215.0
    assert [(s.allocation.seller, s.allocation.qty) for s in run.settlements] == [
        ("Farm A", 200),
        ("Farm B", 300),
    ]
    response = format_procurement_response(run)
    assert "Agent trace:" in response
    assert "Registry returned 2 seller addresses." in response
    assert "Sent QuoteRequest to farm agent agent-farm-a." in response
    assert "Sent PurchaseOrder to Farm A agent at agent-farm-a." in response
    assert "through live agent messages" in response
    assert isinstance(ctx.sent[0][1], WhoSells)
    assert any(isinstance(message, PaymentSent) for _destination, message in ctx.sent)


def test_agent_network_overlays_business_quote_on_responding_farmer() -> None:
    from agents.optimizer import Quote

    ctx = FakeContext()
    # Business Agent undercuts Farm A's network quote (0.40 -> 0.25).
    live = Quote(seller="Farm A", item="tomatoes", qty_available=200, unit_price=0.25)
    run = asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="simulated",
            intent_mode="local",
            wallet=object(),
            business_quote=live,
        )
    )

    farm_a = next(q for q in run.quotes if q.seller == "Farm A")
    assert farm_a.unit_price == 0.25  # live price overlaid onto the responding farmer


def test_agent_network_ignores_business_quote_for_absent_seller() -> None:
    from agents.optimizer import Quote

    ctx = FakeContext()
    bogus = Quote(seller="Ghost Farm", item="tomatoes", qty_available=999, unit_price=0.01)
    run = asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="simulated",
            intent_mode="local",
            wallet=object(),
            business_quote=bogus,
        )
    )

    assert all(q.seller != "Ghost Farm" for q in run.quotes)


def test_agent_network_stripe_connect_uses_invoice_connected_accounts(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    ctx = FakeContext()
    run = asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="stripe_connect",
            intent_mode="local",
            wallet=object(),
        )
    )

    assert run.status == "confirmed"
    assert [settlement.payment.recipient for settlement in run.settlements] == [
        "acct_demo_farm_a",
        "acct_demo_farm_b",
    ]


def test_agent_network_real_checkout_defers_purchase_orders(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    funding = BuyerFundingResult(
        order_id="order-agent",
        amount=215.0,
        currency="usd",
        status="unpaid",
        provider="stripe",
        reference="cs_test_agent",
        checkout_url="https://checkout.stripe.test/session",
        simulated=False,
    )
    ctx = FakeContext()

    run = asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="stripe_connect",
            intent_mode="local",
            wallet=object(),
            buyer_funding_override=funding,
        )
    )

    assert run.status == "payment_pending"
    assert run.settlements == ()
    assert any(isinstance(message, WhoSells) for _destination, message in ctx.sent)
    assert any(isinstance(message, QuoteRequest) for _destination, message in ctx.sent)
    assert not any(message.__class__.__name__ == "PurchaseOrder" for _destination, message in ctx.sent)


def test_agent_network_confirm_paid_checkout_sends_purchase_orders(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGRIBROKER_BUYER_PAYMENT_MODE", "stripe")
    unpaid_funding = BuyerFundingResult(
        order_id="order-agent",
        amount=215.0,
        currency="usd",
        status="unpaid",
        provider="stripe",
        reference="cs_test_agent",
        checkout_url="https://checkout.stripe.test/session",
        simulated=False,
    )
    ctx = FakeContext()
    asyncio.run(
        run_procurement_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            buyer_text="I need 500 tomatoes under 250 FET.",
            payment_mode="stripe_connect",
            intent_mode="local",
            wallet=object(),
            buyer_funding_override=unpaid_funding,
        )
    )

    def fake_retrieve_checkout(**_kwargs: object) -> BuyerFundingResult:
        return BuyerFundingResult(
            order_id="order-agent",
            amount=215.0,
            currency="usd",
            status="paid",
            provider="stripe",
            reference="cs_test_agent",
            checkout_url=None,
            simulated=False,
        )

    monkeypatch.setattr("agents.agent_network.retrieve_stripe_checkout_session", fake_retrieve_checkout)
    ctx.sent.clear()
    run = asyncio.run(
        confirm_pending_order_via_agents(
            ctx=ctx,
            registry_address="agent-registry",
            order_id="order-agent",
            payment_mode="stripe_connect",
            intent_mode="local",
            wallet=object(),
        )
    )

    assert run is not None
    assert run.status == "confirmed"
    assert any(message.__class__.__name__ == "PurchaseOrder" for _destination, message in ctx.sent)
    assert any(isinstance(message, PaymentSent) for _destination, message in ctx.sent)
