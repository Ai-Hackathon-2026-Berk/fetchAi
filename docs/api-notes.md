# Fetch Integration Notes

This file tracks the external Fetch.ai API details that must be verified before the live demo.

## Current Assumptions

- Code agents use `uagents.Agent`, `uagents.Context`, and `uagents.Model`.
- Local development can use custom `Model` messages for registry, quotes, invoices, payments, and receipts.
- ASI:One is used for buyer intent parsing.
- Agentverse hosts/discovers the final code agents.
- The buyer funds the orchestrator first; the orchestrator then pays selected farms.
- Local payment simulation is acceptable as a fallback, but the target demo should show at least orchestrator-to-farm testnet transfers.

## Current Verified Shapes

- ASI:One-compatible agents use the Agent Chat Protocol from `uagents_core.contrib.protocols.chat`.
- The manual wrapper should import `ChatMessage`, `ChatAcknowledgement`, `TextContent`, `EndSessionContent`, and `chat_protocol_spec`.
- The ASI-facing agent should run with `mailbox=True` and `publish_agent_details=True`.
- The chat protocol should be included with `agent.include(protocol, publish_manifest=True)`.
- Current token-send examples use `ctx.ledger.send_tokens(wallet_address, amount, denom, wallet)` and `atestfet`.

## Payment Verification Checklist

- Confirm current testnet denomination and precision.
- Confirm whether `ctx.ledger.send_tokens(...)` or `ledger.send_tokens(...)` is the right current API.
- Confirm whether transaction completion is handled through `wait_for_tx_to_complete(...)`, `tx.wait_to_complete()`, or another helper.
- Confirm faucet flow for funding demo wallets.
- Confirm where transaction links can be viewed for judge-facing receipts.
- Decide whether buyer-to-orchestrator funding is real, pre-funded, or simulated in ASI:One.

## Chat Protocol Verification Checklist

- Confirm the current package/import path for ASI:One Chat Protocol support.
- Confirm how to stream intermediate messages from an orchestrator agent.
- Confirm Agentverse profile metadata needed for ASI:One discovery.
- Confirm how a code uAgent can contact a Flockx Business Agent, if supported.

## Useful Docs

- uAgents docs: https://uagents.fetch.ai/docs
- ASI:One compatible agent: https://uagents.fetch.ai/docs/examples/asi-1
- Agentverse Mailbox: https://uagents.fetch.ai/docs/agentverse/mailbox
- Sending tokens: https://uagents.fetch.ai/docs/guides/send_tokens
- Agent Payment Protocol: https://uagents.fetch.ai/docs/guides/agent-payment-protocol
- Agentverse docs: https://innovationlab.fetch.ai/resources/docs

