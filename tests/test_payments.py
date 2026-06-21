import asyncio
import sys
import types

import pytest

from agents.payments import (
    PaymentResult,
    STRIPE_CONNECT_FARM_PAYMENT_MODE,
    TESTNET_PAYMENT_MODE,
    create_stripe_checkout_session,
    create_stripe_connect_transfer,
    fet_to_micro_fet,
    fund_order_from_buyer,
    get_buyer_payment_mode,
    get_payment_mode,
    micro_fet_to_fet,
    send_fet_with_retries,
    settle_farm_payment,
    wallet_address,
)


def _install_fake_stripe_transfer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    transfer_id: str = "tr_test_123",
    raises: Exception | None = None,
) -> dict[str, object]:
    """Install a fake ``stripe`` module whose ``Transfer.create`` is recorded."""

    created: dict[str, object] = {}

    class FakeTransfer:
        id = transfer_id

    class FakeTransferAPI:
        @staticmethod
        def create(**kwargs: object) -> "FakeTransfer":
            created.update(kwargs)
            if raises is not None:
                raise raises
            return FakeTransfer()

    fake_stripe = types.SimpleNamespace(api_key=None, Transfer=FakeTransferAPI)
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    return created


class FakeTx:
    tx_hash = "ABC123"

    def wait_to_complete(self) -> None:
        return None


class FakeLedger:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, int, str, object]] = []

    def send_tokens(self, recipient: str, amount: int, denom: str, wallet: object) -> FakeTx:
        self.calls.append((recipient, amount, denom, wallet))
        if self.fail:
            raise RuntimeError("chain unavailable")
        return FakeTx()


def test_get_payment_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        get_payment_mode("cash")


def test_get_buyer_payment_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        get_buyer_payment_mode("wire")


def test_fet_unit_conversion() -> None:
    assert fet_to_micro_fet(1.25) == 1_250_000
    assert micro_fet_to_fet(1_250_000) == 1.25


def test_wallet_address_helper_accepts_callable_address() -> None:
    class FakeWallet:
        def address(self) -> str:
            return "fetch1demo"

    assert wallet_address(FakeWallet()) == "fetch1demo"


def test_stripe_checkout_falls_back_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    result = create_stripe_checkout_session(
        order_id="order-1",
        item="tomatoes",
        qty=500,
        amount=215.0,
    )

    assert result.provider == "stripe"
    assert result.simulated
    assert result.reference.startswith("cs_simulated_")
    assert "STRIPE_SECRET_KEY missing" in (result.reason or "")


def test_stripe_checkout_session_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSession:
        id = "cs_test_123"
        url = "https://checkout.stripe.test/session"
        payment_status = "unpaid"

    created: dict[str, object] = {}

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs: object) -> FakeSession:
            created.update(kwargs)
            return FakeSession()

    fake_stripe = types.SimpleNamespace(
        api_key=None,
        checkout=types.SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")

    result = fund_order_from_buyer(
        order_id="order-1",
        item="tomatoes",
        qty=500,
        amount=215.0,
        mode="stripe",
    )

    assert result.provider == "stripe"
    assert result.reference == "cs_test_123"
    assert result.checkout_url == "https://checkout.stripe.test/session"
    assert created["client_reference_id"] == "order-1"
    assert created["mode"] == "payment"


def test_real_payment_result_has_explorer_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FETCH_EXPLORER_TX_URL", "https://example.test/tx")
    result = PaymentResult(
        order_id="order-1",
        recipient="fetch1farm",
        amount_fet=1.0,
        tx_hash="ABC123",
        status="real_confirmed",
    )

    assert result.explorer_url == "https://example.test/tx/ABC123"
    assert result.receipt_ref == "https://example.test/tx/ABC123"


def test_send_fet_with_retries_converts_to_micro_units() -> None:
    ledger = FakeLedger()
    wallet = object()

    result = asyncio.run(
        send_fet_with_retries(
            order_id="order-1",
            ledger=ledger,
            wallet=wallet,
            recipient="fetch1farm",
            amount_fet=1.25,
            retry_delay_seconds=0,
        )
    )

    assert result.status == "real_confirmed"
    assert result.tx_hash == "ABC123"
    assert ledger.calls == [("fetch1farm", 1_250_000, "atestfet", wallet)]


def test_testnet_settlement_falls_back_when_ledger_fails() -> None:
    result = asyncio.run(
        settle_farm_payment(
            order_id="order-1",
            recipient="fetch1farm",
            amount_fet=2.0,
            mode=TESTNET_PAYMENT_MODE,
            ledger=FakeLedger(fail=True),
            wallet=object(),
            reason="test",
        )
    )

    assert result.simulated
    assert result.status == "simulated_confirmed"
    assert result.reason == "chain unavailable"


def test_stripe_connect_falls_back_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "true")

    result = create_stripe_connect_transfer(
        order_id="order-1",
        recipient_account_id="acct_demo_farm_a",
        amount=86.0,
    )

    assert result.simulated
    assert result.status == "simulated_confirmed"
    assert result.tx_hash.startswith("tr_simulated_")
    assert "STRIPE_SECRET_KEY missing" in (result.reason or "")


def test_stripe_connect_falls_back_when_transfers_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "false")

    result = create_stripe_connect_transfer(
        order_id="order-1",
        recipient_account_id="acct_demo_farm_a",
        amount=86.0,
    )

    assert result.simulated
    assert result.tx_hash.startswith("tr_simulated_")
    assert "STRIPE_CONNECT_TRANSFERS_ENABLED" in (result.reason or "")


def test_stripe_connect_falls_back_for_non_connected_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even with Stripe fully enabled, a Fetch wallet address must not reach Stripe.
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "true")

    result = asyncio.run(
        settle_farm_payment(
            order_id="order-1",
            recipient="fetch_demo_farm_a",
            amount_fet=86.0,
            mode=STRIPE_CONNECT_FARM_PAYMENT_MODE,
            reason="payout",
        )
    )

    assert result.simulated
    assert result.reason == "stripe_connect requires a connected account id"


def test_stripe_connect_transfer_creates_real_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    created = _install_fake_stripe_transfer(monkeypatch, transfer_id="tr_test_123")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "true")

    result = create_stripe_connect_transfer(
        order_id="order-1",
        recipient_account_id="acct_demo_farm_a",
        amount=86.0,
        metadata={"settlement_reason": "payout"},
    )

    assert not result.simulated
    assert result.status == "real_confirmed"
    assert result.tx_hash == "tr_test_123"
    assert result.explorer_url is None
    assert result.receipt_ref == "tr_test_123"
    assert result.recipient == "acct_demo_farm_a"
    assert created["amount"] == 8600
    assert created["currency"] == "usd"
    assert created["destination"] == "acct_demo_farm_a"
    assert created["metadata"]["order_id"] == "order-1"
    assert created["metadata"]["recipient_account_id"] == "acct_demo_farm_a"
    assert created["metadata"]["settlement_reason"] == "payout"


def test_stripe_connect_transfer_falls_back_on_stripe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_stripe_transfer(monkeypatch, raises=RuntimeError("connect boom"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "true")

    result = create_stripe_connect_transfer(
        order_id="order-1",
        recipient_account_id="acct_demo_farm_a",
        amount=86.0,
    )

    assert result.simulated
    assert result.status == "simulated_confirmed"
    assert "connect boom" in (result.reason or "")
    assert "Stripe Connect transfer failed" in (result.reason or "")
