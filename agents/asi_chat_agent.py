"""ASI:One-compatible Chat Protocol entry point for AgriBroker."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from agents.agent_network import confirm_pending_order_via_agents, run_procurement_via_agents
from agents.business_seller import (
    build_quote_request_text,
    business_fallback_enabled,
    business_live_quote_enabled,
    business_seller_address,
    business_seller_enabled,
    clear_pending_reply,
    is_awaiting_reply,
    quote_from_reply,
    register_pending_reply,
    resolve_pending_reply,
)
from agents.farm_state import FarmState
from agents.agentverse_profiles import image_kwargs
from agents.llm import parse_buyer_intent, use_mock_intent_parser
from agents.settings import discovery_mode, registry_address
from agents.settings import fetch_network
from agents.workflow import (
    ProcurementRun,
    confirm_pending_order,
    format_procurement_response,
    load_farms,
    run_procurement,
    run_business_procurement,
)

try:  # pragma: no cover - optional local convenience.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

try:  # pragma: no cover - environment convenience for local Agentverse SSL.
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:  # pragma: no cover
    pass

try:  # pragma: no cover - requires live uAgents runtime.
    from uagents import Agent, Context, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        EndSessionContent,
        TextContent,
        chat_protocol_spec,
    )
except Exception:  # pragma: no cover - keeps tests importable without uagents installed.
    Agent = None  # type: ignore[assignment]
    Context = object  # type: ignore[assignment]
    Protocol = None  # type: ignore[assignment]
    ChatAcknowledgement = None  # type: ignore[assignment]
    ChatMessage = None  # type: ignore[assignment]
    EndSessionContent = None  # type: ignore[assignment]
    TextContent = None  # type: ignore[assignment]
    chat_protocol_spec = None  # type: ignore[assignment]


DEFAULT_SEED = "agribroker-orchestrator-demo-seed-change-before-deploy"
AGENT_DESCRIPTION = (
    "Autonomous produce procurement agent that discovers farms, compares quotes, "
    "optimizes split orders, coordinates buyer funding, and returns receipts."
)
AGENT_TAGS = [
    "procurement",
    "produce",
    "marketplace",
    "payments",
    "ASI:One",
    "uAgents",
]
PROGRESS_INTRO = "\U0001f50e On it — discovering farms and collecting live quotes…"
PROGRESS_CONFIRM = "\U0001f504 Confirming your Stripe payment and releasing farm payouts…"
BUSINESS_PROGRESS = "\U0001f4ac Asking Sunny Acres (verified Business Agent) for a live quote…"
_LIVE_FARMS: list[FarmState] | None = None


def business_quote_timeout() -> float:
    try:
        return float(os.getenv("AGRIBROKER_BUSINESS_QUOTE_TIMEOUT", "40"))
    except ValueError:
        return 40.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_text_from_chat_message(msg: object) -> str:
    content = getattr(msg, "content", [])
    chunks: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            chunks.append(text)
    return " ".join(chunks).strip()


def build_failure_response(error: Exception) -> str:
    return (
        "AgriBroker could not complete this procurement request.\n\n"
        f"Reason: {error}\n\n"
        "Try a prompt like: I need 500 tomatoes under $250."
    )


def extract_confirmation_order_id(text: str) -> str | None:
    match = re.search(
        r"\b(?:confirm|confrim)(?:\s+order)?(?:\s+(order-[a-f0-9]{8}))?\b",
        text,
        re.I,
    )
    if match:
        return match.group(1) or ""
    if re.search(r"\b(i paid|payment complete|checkout complete|confirm payment)\b", text, re.I):
        return ""
    return None


def live_farms() -> list[FarmState]:
    global _LIVE_FARMS
    if _LIVE_FARMS is None:
        _LIVE_FARMS = load_farms()
    return _LIVE_FARMS


def reset_live_farms() -> None:
    global _LIVE_FARMS
    _LIVE_FARMS = None


def fallback_business_quote(text: str):
    intent = parse_buyer_intent(
        text,
        use_mock=use_mock_intent_parser(os.getenv("AGRIBROKER_INTENT_MODE", "local")),
    )
    seller_name = os.getenv("AGRIBROKER_BUSINESS_SELLER_NAME", "Sunny Acres").strip() or "Sunny Acres"
    farm = next((farm for farm in load_farms() if farm.name == seller_name and farm.has_item(intent.item)), None)
    if farm is None:
        return None
    return farm.quote(intent.item, intent.qty)


def chat_progress_enabled() -> bool:
    value = os.getenv("AGRIBROKER_CHAT_PROGRESS", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def agentverse_readme_path() -> str | None:
    path = "docs/agentverse-profile.md"
    return path if os.path.exists(path) else None


def build_text_chat_message(text: str, *, end_session: bool = False):
    if ChatMessage is None or TextContent is None or EndSessionContent is None:
        raise RuntimeError("Chat Protocol types are unavailable")

    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=utc_now(), msg_id=uuid4(), content=content)


def build_reasoning_messages(run: ProcurementRun) -> list[str]:
    """Turn a completed run into the orchestrator's step-by-step 'thinking' lines.

    These stream into the ASI:One chat before the final receipt so judges watch the
    agent discover sellers, compare quotes, and optimize the split with real numbers.
    """

    item = run.intent.item
    messages = [f"\U0001f50e Found {len(run.quotes)} seller(s) offering {item}."]

    if run.quotes:
        quote_summary = " · ".join(
            f"{quote.seller} {quote.qty_available}@{quote.unit_price:.2f}"
            for quote in run.quotes
        )
        messages.append(f"\U0001f4ac Quotes: {quote_summary}")

    if run.split.allocations:
        plan = " + ".join(
            f"{allocation.qty}×{allocation.seller}" for allocation in run.split.allocations
        )
        messages.append(f"\U0001f9ee Optimal split: {plan}")

    status = run.status
    if status == "partial":
        messages.append(
            f"⚠️ Only {run.split.allocated_qty} of {run.intent.qty} {item} "
            f"available — short {run.split.shortfall}. No payment sent."
        )
    elif status == "over_budget":
        messages.append("⚠️ Cheapest plan exceeds your budget — no payment sent.")
    elif status == "payment_pending":
        messages.append(
            "\U0001f4b3 Buyer funding via Stripe Checkout — confirm payment to release farm payouts."
        )
    elif run.settlements:
        messages.append(f"\U0001f4b8 Settling {len(run.settlements)} farm payout(s)…")

    return messages


async def send_intro_message(ctx: Context, sender: str, text: str) -> None:
    if not chat_progress_enabled():
        return
    await ctx.send(sender, build_text_chat_message(text))


async def send_progress_messages(ctx: Context, sender: str) -> None:
    """Backward-compatible wrapper for older chat handler paths."""

    await send_intro_message(ctx, sender, PROGRESS_INTRO)


async def send_reasoning_messages(ctx: Context, sender: str, run: ProcurementRun) -> None:
    if not chat_progress_enabled():
        return
    for text in build_reasoning_messages(run):
        await ctx.send(sender, build_text_chat_message(text))


async def fetch_business_quote(ctx: Context, *, qty: int, item: str):  # pragma: no cover - live runtime
    """Ask the Sunny Acres Business Agent for a live quote over the Chat Protocol.

    Chat replies are asynchronous: we send the request, then wait on a per-sender
    future that ``handle_chat_message`` resolves when the Business Agent answers.
    Returns a parsed ``Quote`` or None on timeout/parse-failure, so the caller falls
    back to the seeded Sunny Acres catalog price. The demo never blocks on this.
    """

    address = business_seller_address()
    if not address:
        return None

    future = register_pending_reply(address)
    try:
        await ctx.send(address, build_text_chat_message(build_quote_request_text(qty, item)))
        ctx.logger.info(f"Sent live quote request to Business Agent {address}")
        reply_text = await asyncio.wait_for(future, timeout=business_quote_timeout())
        ctx.logger.info(f"Business Agent replied: {reply_text[:160]!r}")
    except asyncio.TimeoutError:
        ctx.logger.warning("Business Agent did not reply within timeout; using fallback price.")
        return None
    except Exception as exc:
        ctx.logger.warning(f"Business Agent quote request failed ({exc}); using fallback price.")
        return None
    finally:
        clear_pending_reply(address)

    return quote_from_reply(reply_text, qty=qty, item=item)


async def maybe_fetch_business_quote(ctx: Context, sender: str, text: str):  # pragma: no cover - live runtime
    """Best-effort live Business Agent quote with user-visible progress + fallback."""

    if not business_seller_enabled() or not business_live_quote_enabled():
        return None
    try:
        intent = parse_buyer_intent(
            text, use_mock=use_mock_intent_parser(os.getenv("AGRIBROKER_INTENT_MODE", "local"))
        )
    except Exception:
        return None

    await send_intro_message(ctx, sender, BUSINESS_PROGRESS)
    quote = await fetch_business_quote(ctx, qty=intent.qty, item=intent.item)
    if quote is not None:
        await send_intro_message(
            ctx,
            sender,
            f"✅ Sunny Acres replied live: {quote.qty_available} @ {quote.unit_price:.2f}.",
        )
    else:
        await send_intro_message(
            ctx,
            sender,
            "ℹ️ Sunny Acres Business Agent didn't quote in time — using its catalog price.",
        )
    return quote


def create_asi_chat_agent(seed: str | None = None, port: int | None = None):
    if Agent is None or Protocol is None:
        raise RuntimeError(
            "uagents and uagents-core are required for ASI:One chat. "
            "Install dependencies with: python -m pip install -r requirements.txt"
        )

    agent_seed = seed or os.getenv("ORCHESTRATOR_SEED") or DEFAULT_SEED
    agent_port = port or int(os.getenv("ORCHESTRATOR_PORT", "8200"))
    agent = Agent(
        name="agribroker",
        seed=agent_seed,
        port=agent_port,
        mailbox=True,
        publish_agent_details=True,
        network=fetch_network(),
        description=AGENT_DESCRIPTION,
        handle="agribroker",
        readme_path=agentverse_readme_path(),
        **image_kwargs("chat", seed="agribroker-chat"),
        metadata={
            "tags": AGENT_TAGS,
            "category": "procurement",
            "demo_prompt": "I need 500 tomatoes under $250.",
        },
    )
    protocol = Protocol(spec=chat_protocol_spec)

    @agent.on_event("startup")
    async def startup(ctx: Context) -> None:
        ctx.logger.info(f"AgriBroker ASI chat agent address: {ctx.agent.address}")
        ctx.logger.info(f"AgriBroker ASI chat wallet: {agent.wallet.address()}")

    @protocol.on_message(ChatMessage)
    async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
        await ctx.send(
            sender,
            ChatAcknowledgement(timestamp=utc_now(), acknowledged_msg_id=msg.msg_id),
        )

        text = extract_text_from_chat_message(msg)

        # A message from the Business Agent is its reply to our live quote request,
        # not a buyer request — hand it to the waiting future and stop.
        business_address = business_seller_address()
        if business_address and sender == business_address:
            resolve_pending_reply(business_address, text)
            return

        try:
            confirm_order_id = extract_confirmation_order_id(text)
            if confirm_order_id is not None:
                await send_intro_message(ctx, sender, PROGRESS_CONFIRM)
                mode = discovery_mode()
                address = registry_address()
                if mode == "agent" and address:
                    run = await confirm_pending_order_via_agents(
                        ctx=ctx,
                        registry_address=address,
                        order_id=confirm_order_id or None,
                        payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                        intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                        wallet=agent.wallet,
                    )
                else:
                    run = await confirm_pending_order(
                        confirm_order_id or None,
                        farms=live_farms(),
                        payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                        intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                        ledger=getattr(ctx, "ledger", None),
                        wallet=agent.wallet,
                    )
                if run is None:
                    response = (
                        "I could not find a pending Stripe Checkout order to confirm.\n\n"
                        "Start a new request with: I need 500 tomatoes under $250."
                    )
                else:
                    response = format_procurement_response(run)
                await ctx.send(sender, build_text_chat_message(response, end_session=True))
                return

            await send_intro_message(ctx, sender, PROGRESS_INTRO)
            # Live Business Agent quote runs in BOTH discovery modes.
            business_quote = await maybe_fetch_business_quote(ctx, sender, text)
            mode = discovery_mode()
            address = registry_address()
            if mode == "business":
                used_business_fallback = False
                if business_quote is None:
                    if not business_fallback_enabled():
                        raise ValueError(
                            "Business-only mode requires a live Sunny Acres Business Agent quote. "
                            "Set AGRIBROKER_BUSINESS_SELLER_ADDRESS and make sure Sunny Acres replies."
                        )
                    business_quote = fallback_business_quote(text)
                    if business_quote is None:
                        raise ValueError(
                            "Business-only fallback could not find the Sunny Acres catalog quote."
                        )
                    used_business_fallback = True
                run = await run_business_procurement(
                    text,
                    business_quote=business_quote,
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                )
                if used_business_fallback:
                    run = ProcurementRun(
                        order_id=run.order_id,
                        intent=run.intent,
                        quotes=run.quotes,
                        split=run.split,
                        buyer_funding=run.buyer_funding,
                        settlements=run.settlements,
                        transcript=(
                            *run.transcript,
                            "Business Agent live reply timed out; used Sunny Acres configured Business catalog fallback.",
                        ),
                        payment_mode=run.payment_mode,
                        buyer_payment_mode=run.buyer_payment_mode,
                    )
            elif mode == "agent" and address:
                run = await run_procurement_via_agents(
                    ctx=ctx,
                    registry_address=address,
                    buyer_text=text,
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    wallet=agent.wallet,
                    business_quote=business_quote,
                )
            else:
                run = await run_procurement(
                    text,
                    farms=live_farms(),
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    ledger=getattr(ctx, "ledger", None),
                    wallet=agent.wallet,
                    business_quote=business_quote,
                )
            await send_reasoning_messages(ctx, sender, run)
            response = format_procurement_response(run)
        except Exception as exc:
            ctx.logger.exception("AgriBroker chat request failed")
            response = build_failure_response(exc)

        await ctx.send(sender, build_text_chat_message(response, end_session=True))

    @protocol.on_message(ChatAcknowledgement)
    async def handle_chat_ack(_ctx: Context, _sender: str, _msg: ChatAcknowledgement) -> None:
        return None

    agent.include(protocol, publish_manifest=True)
    return agent


if __name__ == "__main__":  # pragma: no cover - requires live uAgents runtime.
    create_asi_chat_agent().run()
