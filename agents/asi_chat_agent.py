"""ASI:One-compatible Chat Protocol entry point for AgriBroker."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from agents.workflow import format_procurement_response, run_procurement

try:  # pragma: no cover - optional local convenience.
    from dotenv import load_dotenv

    load_dotenv()
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
        "Try a prompt like: I need 500 tomatoes under 250 FET."
    )


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
            run = await run_procurement(
                text,
                payment_mode=os.getenv("AGRIBROKER_PAYMENT_MODE", "simulated"),
                ledger=getattr(ctx, "ledger", None),
                wallet=agent.wallet,
            )
            response = format_procurement_response(run)
        except Exception as exc:
            ctx.logger.exception("AgriBroker chat request failed")
            response = build_failure_response(exc)

        await ctx.send(
            sender,
            ChatMessage(
                timestamp=utc_now(),
                msg_id=uuid4(),
                content=[
                    TextContent(type="text", text=response),
                    EndSessionContent(type="end-session"),
                ],
            ),
        )

    @protocol.on_message(ChatAcknowledgement)
    async def handle_chat_ack(_ctx: Context, _sender: str, _msg: ChatAcknowledgement) -> None:
        return None

    agent.include(protocol, publish_manifest=True)
    return agent


if __name__ == "__main__":  # pragma: no cover - requires live uAgents runtime.
    create_asi_chat_agent().run()
