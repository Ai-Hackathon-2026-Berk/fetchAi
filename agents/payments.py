"""Payment helpers for buyer funding and farm settlement."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

PaymentMode = str
BuyerPaymentMode = str

SIMULATED_PAYMENT_MODE = "simulated"
TESTNET_PAYMENT_MODE = "testnet"
STRIPE_CONNECT_FARM_PAYMENT_MODE = "stripe_connect"
VALID_PAYMENT_MODES = {
    SIMULATED_PAYMENT_MODE,
    TESTNET_PAYMENT_MODE,
    STRIPE_CONNECT_FARM_PAYMENT_MODE,
}
STRIPE_BUYER_PAYMENT_MODE = "stripe"
VALID_BUYER_PAYMENT_MODES = {SIMULATED_PAYMENT_MODE, STRIPE_BUYER_PAYMENT_MODE}
MICRO_FET = 1_000_000


def _stripe_connect_transfers_enabled() -> bool:
    """Connect transfers are an explicit opt-in so the demo never moves real money by accident."""
    return os.getenv("STRIPE_CONNECT_TRANSFERS_ENABLED", "").strip().lower() == "true"


@dataclass(frozen=True, slots=True)
class PaymentResult:
    order_id: str
    recipient: str
    amount_fet: float
    tx_hash: str
    status: str
    simulated: bool = False
    reason: str | None = None

    @property
    def explorer_url(self) -> str | None:
        if self.simulated:
            return None
        if self.tx_hash.startswith("tr_"):
            return None
        base_url = os.getenv("FETCH_EXPLORER_TX_URL", "https://explore-fetchhub.fetch.ai/transactions")
        return f"{base_url.rstrip('/')}/{self.tx_hash}"

    @property
    def receipt_ref(self) -> str:
        return self.tx_hash if self.explorer_url is None else self.explorer_url


@dataclass(frozen=True, slots=True)
class BuyerFundingResult:
    order_id: str
    amount: float
    currency: str
    status: str
    provider: str
    reference: str
    checkout_url: str | None = None
    simulated: bool = False
    reason: str | None = None

    @property
    def receipt_ref(self) -> str:
        if self.checkout_url:
            return self.checkout_url
        return self.reference


class PaymentError(RuntimeError):
    pass


def get_payment_mode(value: str | None = None) -> PaymentMode:
    mode = (
        value
        or os.getenv("AGRIBROKER_FARM_PAYMENT_MODE")
        or os.getenv("AGRIBROKER_PAYMENT_MODE")
        or SIMULATED_PAYMENT_MODE
    ).strip().lower()
    if mode not in VALID_PAYMENT_MODES:
        raise ValueError(
            f"Unsupported payment mode {mode!r}. Use one of: {', '.join(sorted(VALID_PAYMENT_MODES))}"
        )
    return mode


def get_buyer_payment_mode(value: str | None = None) -> BuyerPaymentMode:
    mode = (value or os.getenv("AGRIBROKER_BUYER_PAYMENT_MODE") or SIMULATED_PAYMENT_MODE).strip().lower()
    if mode not in VALID_BUYER_PAYMENT_MODES:
        raise ValueError(
            f"Unsupported buyer payment mode {mode!r}. Use one of: "
            f"{', '.join(sorted(VALID_BUYER_PAYMENT_MODES))}"
        )
    return mode


def simulated_payment(
    order_id: str,
    recipient: str,
    amount_fet: float,
    reason: str | None = None,
) -> PaymentResult:
    return PaymentResult(
        order_id=order_id,
        recipient=recipient,
        amount_fet=amount_fet,
        tx_hash=f"simulated-{uuid4().hex[:16]}",
        status="simulated_confirmed",
        simulated=True,
        reason=reason,
    )


def simulated_buyer_funding(
    order_id: str,
    amount: float,
    currency: str = "usd",
    reason: str | None = None,
) -> BuyerFundingResult:
    return BuyerFundingResult(
        order_id=order_id,
        amount=amount,
        currency=currency,
        status="simulated_confirmed",
        provider="simulated",
        reference=f"simulated-{uuid4().hex[:16]}",
        simulated=True,
        reason=reason,
    )


def simulated_stripe_buyer_funding(
    order_id: str,
    amount: float,
    currency: str = "usd",
    reason: str | None = None,
) -> BuyerFundingResult:
    return BuyerFundingResult(
        order_id=order_id,
        amount=amount,
        currency=currency,
        status="simulated_checkout_created",
        provider="stripe",
        reference=f"cs_simulated_{uuid4().hex[:16]}",
        simulated=True,
        reason=reason,
    )


def no_buyer_funding(
    order_id: str,
    reason: str,
    currency: str = "usd",
) -> BuyerFundingResult:
    return BuyerFundingResult(
        order_id=order_id,
        amount=0.0,
        currency=currency,
        status="not_requested",
        provider="none",
        reference="not requested",
        simulated=True,
        reason=reason,
    )


def create_stripe_checkout_session(
    *,
    order_id: str,
    item: str,
    qty: int,
    amount: float,
    currency: str = "usd",
) -> BuyerFundingResult:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        return simulated_stripe_buyer_funding(
            order_id,
            amount,
            currency=currency,
            reason="STRIPE_SECRET_KEY missing; simulated Stripe Checkout",
        )

    try:
        import stripe

        stripe.api_key = secret_key
        _configure_stripe_timeout(stripe)
        success_url = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/agribroker/success")
        cancel_url = os.getenv("STRIPE_CANCEL_URL", "https://example.com/agribroker/cancel")
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=order_id,
            metadata={"order_id": order_id, "item": item, "qty": str(qty)},
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "unit_amount": dollars_to_cents(amount),
                        "product_data": {
                            "name": f"AgriBroker order: {qty} {item}",
                            "description": "Buyer funding for autonomous produce procurement",
                        },
                    },
                    "quantity": 1,
                }
            ],
        )
        return BuyerFundingResult(
            order_id=order_id,
            amount=amount,
            currency=currency,
            status=str(getattr(session, "payment_status", "checkout_created")),
            provider="stripe",
            reference=str(session.id),
            checkout_url=str(session.url),
            simulated=False,
        )
    except Exception as exc:
        return simulated_stripe_buyer_funding(
            order_id,
            amount,
            currency=currency,
            reason=f"Stripe Checkout failed; simulated Checkout: {exc}",
        )


def fund_order_from_buyer(
    *,
    order_id: str,
    item: str,
    qty: int,
    amount: float,
    mode: BuyerPaymentMode,
    currency: str = "usd",
) -> BuyerFundingResult:
    if mode == STRIPE_BUYER_PAYMENT_MODE:
        return create_stripe_checkout_session(
            order_id=order_id,
            item=item,
            qty=qty,
            amount=amount,
            currency=currency,
        )
    return simulated_buyer_funding(
        order_id,
        amount,
        currency=currency,
        reason="local demo buyer funding",
    )


def retrieve_stripe_checkout_session(
    *,
    session_id: str,
    order_id: str,
    amount: float,
    currency: str = "usd",
) -> BuyerFundingResult:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        return simulated_stripe_buyer_funding(
            order_id,
            amount,
            currency=currency,
            reason="STRIPE_SECRET_KEY missing; cannot verify Checkout session",
        )

    try:
        import stripe

        stripe.api_key = secret_key
        _configure_stripe_timeout(stripe)
        session = stripe.checkout.Session.retrieve(session_id)
        raw_checkout_url = getattr(session, "url", None)
        checkout_url = raw_checkout_url if isinstance(raw_checkout_url, str) and raw_checkout_url else None
        return BuyerFundingResult(
            order_id=order_id,
            amount=amount,
            currency=currency,
            status=str(getattr(session, "payment_status", "unknown")),
            provider="stripe",
            reference=str(getattr(session, "id", session_id)),
            checkout_url=checkout_url,
            simulated=False,
        )
    except Exception as exc:
        return simulated_stripe_buyer_funding(
            order_id,
            amount,
            currency=currency,
            reason=f"Stripe Checkout verification failed: {exc}",
        )


def create_stripe_connect_transfer(
    order_id: str,
    recipient_account_id: str,
    amount: float,
    currency: str = "usd",
    metadata: dict[str, str] | None = None,
) -> PaymentResult:
    """Pay a farm via a Stripe Connect transfer, with a simulated fallback.

    This mirrors the real Connect flow: the buyer funds the platform with Stripe
    Checkout, then the platform transfers a share to each seller's *connected
    account* (``acct_...``). It is demo-safe by construction: a real
    ``stripe.Transfer.create`` only runs when BOTH ``STRIPE_SECRET_KEY`` is set
    AND ``STRIPE_CONNECT_TRANSFERS_ENABLED=true``. Any other state, or any Stripe
    error, returns a clearly labeled simulated ``PaymentResult`` so a missing key
    or flaky API never breaks the live demo.

    ``amount`` is a fiat amount in ``currency`` (USD by default). We reuse
    ``PaymentResult`` for a uniform settlement type across payout backends; its
    ``amount_fet`` field carries the transferred amount and ``tx_hash`` carries
    the Stripe transfer id (``tr_...``).
    """

    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        return simulated_stripe_transfer(
            order_id,
            recipient_account_id,
            amount,
            reason="STRIPE_SECRET_KEY missing; simulated Stripe Connect payout",
        )

    if not _stripe_connect_transfers_enabled():
        return simulated_stripe_transfer(
            order_id,
            recipient_account_id,
            amount,
            reason="STRIPE_CONNECT_TRANSFERS_ENABLED is not 'true'; simulated Stripe Connect payout",
        )

    transfer_metadata: dict[str, str] = {
        "order_id": order_id,
        "recipient_account_id": recipient_account_id,
    }
    if metadata:
        transfer_metadata.update({str(key): str(value) for key, value in metadata.items()})

    try:
        import stripe

        stripe.api_key = secret_key
        _configure_stripe_timeout(stripe)
        transfer = stripe.Transfer.create(
            amount=dollars_to_cents(amount),
            currency=currency,
            destination=recipient_account_id,
            metadata=transfer_metadata,
        )
        return PaymentResult(
            order_id=order_id,
            recipient=recipient_account_id,
            amount_fet=amount,
            tx_hash=str(transfer.id),
            status="real_confirmed",
            simulated=False,
        )
    except Exception as exc:
        return simulated_stripe_transfer(
            order_id,
            recipient_account_id,
            amount,
            reason=f"Stripe Connect transfer failed; simulated payout: {exc}",
        )


def simulated_stripe_transfer(
    order_id: str,
    recipient_account_id: str,
    amount: float,
    reason: str | None = None,
) -> PaymentResult:
    return PaymentResult(
        order_id=order_id,
        recipient=recipient_account_id,
        amount_fet=amount,
        tx_hash=f"tr_simulated_{uuid4().hex[:16]}",
        status="simulated_confirmed",
        simulated=True,
        reason=reason,
    )


def _stripe_api_timeout_seconds() -> float:
    value = os.getenv("STRIPE_API_TIMEOUT_SECONDS", "8")
    try:
        timeout = float(value)
    except ValueError:
        timeout = 8.0
    return max(1.0, timeout)


def _configure_stripe_timeout(stripe_module: Any) -> None:
    requests_client = getattr(stripe_module, "RequestsClient", None)
    if requests_client is None:
        return
    stripe_module.default_http_client = requests_client(timeout=_stripe_api_timeout_seconds())


async def send_fet_with_retries(
    *,
    order_id: str,
    ledger: Any,
    wallet: Any,
    recipient: str,
    amount_fet: float,
    denom: str = "atestfet",
    attempts: int = 3,
    retry_delay_seconds: float = 1.0,
    fallback_to_simulated: bool = True,
) -> PaymentResult:
    """Send testnet FET with retries and simulated fallback.

    ``amount_fet`` is converted to integer micro-units for the ledger call. The
    current uAgents guide uses ``ctx.ledger.send_tokens(address, amount, denom,
    wallet)`` with ``atestfet`` for testnet examples.
    """

    last_error: Exception | None = None
    amount_units = fet_to_micro_fet(amount_fet)

    for attempt in range(1, attempts + 1):
        try:
            tx = ledger.send_tokens(recipient, amount_units, denom, wallet)
            tx_hash = str(getattr(tx, "tx_hash", tx))
            if hasattr(tx, "wait_to_complete"):
                tx.wait_to_complete()
            else:  # pragma: no cover - depends on live uAgents network helpers.
                try:
                    from uagents.network import wait_for_tx_to_complete

                    await wait_for_tx_to_complete(tx_hash, ledger)
                except Exception:
                    pass
            return PaymentResult(
                order_id=order_id,
                recipient=recipient,
                amount_fet=amount_fet,
                tx_hash=tx_hash,
                status="real_confirmed",
            )
        except Exception as exc:  # pragma: no cover - requires live ledger.
            last_error = exc
            if attempt < attempts:
                await asyncio.sleep(retry_delay_seconds * attempt)

    if fallback_to_simulated:
        reason = str(last_error) if last_error else "unknown payment failure"
        return simulated_payment(order_id, recipient, amount_fet, reason=reason)

    raise PaymentError(str(last_error) if last_error else "payment failed")


async def settle_farm_payment(
    *,
    order_id: str,
    recipient: str,
    amount_fet: float,
    mode: PaymentMode,
    ledger: Any | None = None,
    wallet: Any | None = None,
    reason: str,
) -> PaymentResult:
    if mode == STRIPE_CONNECT_FARM_PAYMENT_MODE:
        # Never call Stripe with a Fetch wallet or any other non-Connect destination.
        if not recipient.startswith("acct_"):
            return simulated_payment(
                order_id,
                recipient,
                amount_fet,
                reason="stripe_connect requires a connected account id",
            )
        return create_stripe_connect_transfer(
            order_id,
            recipient,
            amount_fet,
            metadata={"settlement_reason": reason},
        )

    if mode == TESTNET_PAYMENT_MODE and ledger is not None and wallet is not None:
        return await send_fet_with_retries(
            order_id=order_id,
            ledger=ledger,
            wallet=wallet,
            recipient=recipient,
            amount_fet=amount_fet,
            denom=os.getenv("FETCH_DENOM", "atestfet"),
        )

    fallback_reason = reason
    if mode == TESTNET_PAYMENT_MODE:
        fallback_reason = "testnet mode requested, but ledger/wallet runtime was unavailable"

    return simulated_payment(
        order_id=order_id,
        recipient=recipient,
        amount_fet=amount_fet,
        reason=fallback_reason,
    )


def fet_to_micro_fet(amount_fet: float) -> int:
    if amount_fet < 0:
        raise ValueError("amount_fet cannot be negative")
    return int(round(amount_fet * MICRO_FET))


def dollars_to_cents(amount: float) -> int:
    if amount < 0:
        raise ValueError("amount cannot be negative")
    return int(round(amount * 100))


def micro_fet_to_fet(amount: int) -> float:
    if amount < 0:
        raise ValueError("amount cannot be negative")
    return amount / MICRO_FET


def wallet_address(wallet: Any) -> str:
    address = getattr(wallet, "address", None)
    if callable(address):
        return str(address())
    if address is not None:
        return str(address)
    raise PaymentError("Could not determine wallet address")


def get_balance_fet(ledger: Any, address: str, denom: str = "atestfet") -> float | None:
    for method_name in ("query_bank_balance", "query_balance"):
        method = getattr(ledger, method_name, None)
        if method is None:
            continue
        try:
            balance = method(address, denom)
            amount = getattr(balance, "amount", balance)
            return micro_fet_to_fet(int(amount))
        except Exception:
            continue
    return None
