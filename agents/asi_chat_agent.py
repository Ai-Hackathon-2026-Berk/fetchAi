"""ASI:One-compatible Chat Protocol entry point for AgriBroker."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from uuid import uuid4

from agents.agent_network import confirm_pending_order_via_agents, run_procurement_via_agents
from agents.farm_state import FarmState
from agents.settings import discovery_mode, registry_address
from agents.settings import fetch_network
from agents.workflow import (
    ProcurementRun,
    confirm_pending_order,
    format_procurement_response,
    load_farms,
    run_procurement,
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
_LIVE_FARMS: list[FarmState] | None = None


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


def chat_progress_enabled() -> bool:
    value = os.getenv("AGRIBROKER_CHAT_PROGRESS", "true").strip().lower()
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
            mode = discovery_mode()
            address = registry_address()
            if mode == "agent" and address:
                run = await run_procurement_via_agents(
                    ctx=ctx,
                    registry_address=address,
                    buyer_text=text,
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    wallet=agent.wallet,
                )
            else:
                run = await run_procurement(
                    text,
                    farms=live_farms(),
                    payment_mode=os.getenv("AGRIBROKER_FARM_PAYMENT_MODE", "simulated"),
                    intent_mode=os.getenv("AGRIBROKER_INTENT_MODE", "local"),
                    ledger=getattr(ctx, "ledger", None),
                    wallet=agent.wallet,
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
