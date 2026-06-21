import asyncio

from agents.agent_network import run_procurement_via_agents
from agents.protocols import Invoice, PaymentSent, QuoteRequest, QuoteResponse, Receipt, SellerList, WhoSells


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
    assert isinstance(ctx.sent[0][1], WhoSells)
    assert any(isinstance(message, PaymentSent) for _destination, message in ctx.sent)


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
