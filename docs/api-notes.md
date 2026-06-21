# Fetch Integration Notes

This file tracks the external Fetch.ai API details that must be verified before the live demo.

## Current Assumptions

- Code agents use `uagents.Agent`, `uagents.Context`, and `uagents.Model`.
- Local development can use custom `Model` messages for registry, quotes, invoices, payments, and receipts.
- ASI:One is used for buyer intent parsing.
- Agentverse hosts/discovers the final code agents.
- The buyer funds the order first through Stripe Checkout or simulated buyer funding; the orchestrator then marks or pays selected farms.
- Local payment simulation is acceptable as a fallback, but the target demo should show at least orchestrator-to-farm testnet transfers.

## Current Verified Shapes

- ASI:One-compatible agents use the Agent Chat Protocol from `uagents_core.contrib.protocols.chat`.
- The manual wrapper should import `ChatMessage`, `ChatAcknowledgement`, `TextContent`, `EndSessionContent`, and `chat_protocol_spec`.
- The ASI-facing agent should run with `mailbox=True` and `publish_agent_details=True`.
- The chat protocol should be included with `agent.include(protocol, publish_manifest=True)`.
- Current token-send examples use `ctx.ledger.send_tokens(wallet_address, amount, denom, wallet)` and `atestfet`.
- Local startup check succeeded with `uagents 0.25.2` and `uagents-core 0.4.7`: the ASI chat agent published the `AgentChatProtocol` manifest and registered active. The remaining manual setup is creating/connecting the mailbox in Agent Inspector.
- `AGRIBROKER_INTENT_MODE=local` is the default for demo determinism. Use `asi` once the ASI:One key and response format are verified.
- `AGRIBROKER_DISCOVERY_MODE=agent` enables the real Registry/Farmer message path through `ctx.send_and_receive`. Keep `local` as the fallback for live demos.
- Stripe Checkout Sessions are the organizer-preferred buyer payment path. The implementation creates a Checkout Session with `mode=payment`, `client_reference_id=order_id`, metadata, one line item, and success/cancel URLs. If `STRIPE_SECRET_KEY` is missing or Stripe fails, buyer funding falls back to simulated mode.
- Stripe Connect transfers are the farm/seller payout path. The buyer funds the platform via Checkout; the platform then transfers each seller's share to their Stripe **connected account** (`acct_...`) with `stripe.Transfer.create(amount, currency, destination, metadata)`. This is gated behind `AGRIBROKER_FARM_PAYMENT_MODE=stripe_connect` and is demo-safe: a real transfer only runs when BOTH `STRIPE_SECRET_KEY` is set AND `STRIPE_CONNECT_TRANSFERS_ENABLED=true`. Any other state, a recipient that is not an `acct_...` id, or any Stripe error falls back to a clearly labeled simulated `PaymentResult`.
- The workflow now carries each farm's `stripe_connected_account_id` from `config/farms.json` into invoices and uses it when `AGRIBROKER_FARM_PAYMENT_MODE=stripe_connect`. The seeded `acct_demo_*` ids are placeholders; replace them with real Stripe test connected accounts before enabling live Connect transfers. Connect payouts reuse `PaymentResult`; its `amount_fet` holds the transferred amount and `tx_hash` holds the Stripe transfer id (`tr_...`). For Stripe transfers, `receipt_ref` remains the transfer id instead of a Fetch explorer link.
- Farmer onboarding can create the connected-account value consumed by payouts. The simulated default returns `acct_demo_<farm_slug>`; the gated real path uses Stripe Connect Express with `stripe.Account.create(type="express", ...)` plus `stripe.AccountLink.create(type="account_onboarding", ...)`. This is controlled by `STRIPE_CONNECT_ONBOARDING_ENABLED`, which is separate from `STRIPE_CONNECT_TRANSFERS_ENABLED`.
- Amount note: Connect transfers and Checkout both treat the optimizer total (denominated in FET) as the fiat charge amount via `dollars_to_cents`, i.e. an implicit 1 FET = 1 USD assumption. Revisit if real FX is needed.

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

## Business Agent Boundary

- Code uAgents are Python agents built with the uAgents framework. They run the reliable procurement backend: registry, farmers, orchestrator, quote messages, invoices, and receipts.
- Fetch/Flockx Business Agents are no-code or workbench-created business storefronts. Sunny Acres is the best candidate for this because it can be presented as a verified tomato seller with natural-language catalog behavior.
- For judging, keep Business Agents out of the critical optimizer path unless direct agent-to-agent access is confirmed. Show Sunny Acres Business Agent as the storefront proof, and keep the code-backed Sunny Acres farm as the live fallback.

## Useful Docs

- uAgents docs: https://uagents.fetch.ai/docs
- ASI:One compatible agent: https://uagents.fetch.ai/docs/examples/asi-1
- Agentverse Mailbox: https://uagents.fetch.ai/docs/agentverse/mailbox
- Sending tokens: https://uagents.fetch.ai/docs/guides/send_tokens
- Agent Payment Protocol: https://uagents.fetch.ai/docs/guides/agent-payment-protocol
- Agentverse docs: https://innovationlab.fetch.ai/resources/docs
- Stripe Checkout Sessions API: https://docs.stripe.com/api/checkout/sessions/create
- Stripe Checkout overview: https://docs.stripe.com/payments/checkout
- Stripe Connect Express onboarding: https://docs.stripe.com/connect/express-accounts
- Stripe Account Links API: https://docs.stripe.com/api/account_links/create
