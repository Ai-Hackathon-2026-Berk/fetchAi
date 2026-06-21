# AgriBroker

Autonomous produce procurement for the Fetch.ai ecosystem.

AgriBroker lets a buyer ask for produce in natural language, then uses agents to discover sellers, gather quotes, compute the cheapest split, fund the order, pay selected farms, and return a single itemized receipt.

Demo prompt:

```text
I need 500 tomatoes under $250.
```

Expected result:

- Farm A supplies 200 tomatoes at $0.40 each.
- Green Valley supplies 300 tomatoes at $0.42 each.
- Total cost is $206.
- The buyer stays under the $250 budget.

## Why It Matters

Bulk buyers should not manually compare suppliers, check stock, split orders, and send separate payments. AgriBroker turns one procurement intent into an agent-run marketplace workflow:

1. Understand the buyer's request.
2. Discover farms selling the requested item.
3. Ask each farm for a live quote.
4. Optimize the cheapest feasible split.
5. Fund the order through the orchestrator.
6. Pay the winning farms.
7. Return a combined receipt.

The current repo includes the local deterministic core plus uAgent entry points. The local flow is intentionally runnable before Agentverse, ASI:One, and live testnet payment credentials are configured.

## Architecture

| Component | Role |
|---|---|
| Orchestrator | Buyer-facing agent. Parses intent, asks for quotes, optimizes, coordinates payment, returns receipt. |
| Registry | Tracks which agents sell which catalog items. |
| Farmer agents | Hold inventory, quote prices, invoice orders, confirm paid purchases. |
| Sunny Acres | Demo verified-brand seller. Use Flockx Business Agent when available; local config includes a code fallback. |
| Optimizer | Pure greedy optimizer for per-unit pricing with no fixed shipping cost. |
| Payment layer | Buyer funds orchestrator; orchestrator pays selected farms. Uses simulated Stripe locally, with optional testnet FET as a Fetch-native stretch. |

## Repo Structure

```text
agents/
  protocols.py             Shared uAgent message models
  optimizer.py             Pure cheapest-split optimizer
  farm_state.py            Farm inventory and pricing behavior
  workflow.py              End-to-end local procurement flow
  llm.py                   ASI:One intent parser with local fallback
  payments.py              Testnet/simulated payment helpers
  registry_agent.py        Registry uAgent
  farmer_agent.py          Parameterized farmer uAgent
  orchestrator_agent.py    Structured orchestrator uAgent
config/
  farms.json               Demo farms, stock, prices, seeds, ports
scripts/
  run_local_demo.py        Local tomatoes procurement demo
tests/
  test_optimizer.py
  test_llm.py
  test_workflow.py
docs/
  api-notes.md             Fetch integration notes and verification checklist
```

## Quickstart

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Run the local demo:

```bash
python scripts/run_local_demo.py
```

You should see a transcript showing intent parsing, quote collection, optimization, buyer funding, farm payouts, and receipts.

Preview the ASI-style response without Agentverse:

```bash
python scripts/preview_asi_response.py
```

Run the demo readiness check:

```bash
python scripts/check_demo_ready.py
```

Print every Agentverse profile, handle, README, and run command:

```bash
python scripts/print_agentverse_profiles.py
```

## ASI:One And Agentverse

The ASI:One entry point is:

```bash
python -m agents.asi_chat_agent
```

This starts a Chat Protocol-compatible uAgent with `mailbox=True` and `publish_agent_details=True`. Keep this process running while testing from ASI:One.

Supporting Registry and Farmer agents also publish Agentverse metadata and README profiles. See [docs/agentverse/setup.md](docs/agentverse/setup.md) for the full profile checklist.

Setup steps:

1. Create `.env` from `.env.example` if needed.
2. Add `ASI_ONE_API_KEY` when you want live ASI:One intent parsing.
3. Keep `AGRIBROKER_INTENT_MODE=local`, `AGRIBROKER_BUYER_PAYMENT_MODE=simulated`, and `AGRIBROKER_FARM_PAYMENT_MODE=simulated` for the first ASI:One test.
4. Run `python -m agents.asi_chat_agent`.
5. Open the Agent Inspector URL printed in the terminal.
6. If logs say `Agent mailbox not found`, that is expected before the first setup. In Inspector, click **Connect** and choose **Mailbox**.
7. Open the Agent Profile in Agentverse.
8. Set the public profile:
   - Name: `AgriBroker`
   - Handle: `@agribroker`
   - Description: `Autonomous produce procurement agent that discovers farms, compares tomato quotes, optimizes split orders, and returns payment receipts.`
   - Tags: `procurement`, `produce`, `marketplace`, `payments`, `Fetch.ai`
9. Click **Chat with Agent** from Agentverse.
10. Send:

```text
I need 500 tomatoes under $250.
```

Expected ASI:One response:

```text
AgriBroker found 5 sellers for tomatoes.

Quotes:
- Farm A: 200 @ $0.40
- Farm B: 400 @ $0.45
- Farm C: 100 @ $0.50
- Sunny Acres: 300 @ $0.48
- Green Valley: 300 @ $0.42

Optimal split:
- Farm A: 200 tomatoes = $80.00
- Green Valley: 300 tomatoes = $126.00

Receipt:
- Total: $206.00
- Budget: $250.00
- Status: confirmed
- Buyer payment: Stripe Checkout (simulated)
- Farm payout mode: Stripe Connect (simulated/local demo)
```

Troubleshooting:

- If the agent cannot bind to `0.0.0.0:8200`, run it from a normal terminal instead of a restricted sandbox, or change `ORCHESTRATOR_PORT`.
- The app automatically points Python at the `certifi` certificate bundle. If Agentverse mailbox logs still show `CERTIFICATE_VERIFY_FAILED`, fix local Python certificates. On macOS python.org installs, run `/Applications/Python 3.13/Install Certificates.command` if present. You can also run:

```bash
export SSL_CERT_FILE="$(python3 -c 'import certifi; print(certifi.where())')"
python -m agents.asi_chat_agent
```

## Payment Model

The intended marketplace payment flow is:

1. Buyer approves the optimized plan.
2. Buyer funds the order through Stripe Checkout.
3. Orchestrator acts as a neutral purchasing agent for that order.
4. Orchestrator pays or marks payout to each winning farm.
5. Farms confirm payment, decrement inventory, and return receipts.
6. Orchestrator returns one combined buyer receipt.

Buyer payment and farm payout are separate modes:

```env
AGRIBROKER_BUYER_PAYMENT_MODE=stripe     # simulated | stripe
AGRIBROKER_FARM_PAYMENT_MODE=simulated   # simulated | testnet | stripe_connect
```

**Buyer funding (Stripe Checkout).** For the organizer-preferred Stripe path, set `AGRIBROKER_BUYER_PAYMENT_MODE=stripe`. With no `STRIPE_SECRET_KEY`, AgriBroker creates a simulated Checkout reference like `cs_simulated_...` and displays dollars in the receipt. With a real test key, it can create a hosted Stripe Checkout Session.

**Farm payouts.** These can remain simulated for demo reliability, use testnet FET as a Fetch-native settlement stretch, or use **Stripe Connect** transfers to pay sellers in fiat. The Connect model is: the buyer funds the platform via Checkout, then the platform transfers each seller's share to their Stripe **connected account** (`acct_...`). Enable it with:

```env
AGRIBROKER_FARM_PAYMENT_MODE=stripe_connect
STRIPE_CONNECT_TRANSFERS_ENABLED=true
```

Connect payouts are off by default and demo-safe: a real `stripe.Transfer.create` only runs when `STRIPE_SECRET_KEY` is set **and** `STRIPE_CONNECT_TRANSFERS_ENABLED=true`. Real payouts also require genuinely onboarded connected accounts. The workflow now carries each farm's `stripe_connected_account_id` from `config/farms.json` into invoices, but the seeded `acct_demo_*` ids are placeholders. Replace them with real Stripe test connected accounts before enabling live Connect transfers. If the network/faucet/Stripe fails during judging, simulated farm payout keeps the workflow alive while making the status explicit.

Useful payment setup commands:

```bash
python scripts/print_agent_addresses.py
python scripts/check_testnet_payment_ready.py
python scripts/check_stripe_ready.py
```

When using a real Stripe test key, run the local Checkout return page server before clicking Checkout links:

```bash
python scripts/serve_checkout_pages.py
```

Stripe redirects successful test payments to `http://127.0.0.1:8787/checkout/success`, which displays an AgriBroker order confirmation page. Use Stripe test card `4242 4242 4242 4242` with any future date and CVC.

Fund the printed orchestrator wallet before switching to:

```env
AGRIBROKER_FARM_PAYMENT_MODE=testnet
```

Keep `AGRIBROKER_FARM_PAYMENT_MODE=simulated` until the orchestrator wallet is funded and at least one testnet payout has been verified.

## Onboarding A Farmer

Farmers can self-onboard into the local marketplace without hand-editing JSON:

```bash
python scripts/onboard_farmer.py --name "Green Valley" --item tomatoes --stock 300 --price 0.42 --floor 0.38 --no-stripe
```

The wizard builds a valid farm entry, validates the full config before writing, appends the farm to `config/farms.json`, and prints the command to bring that seller agent online:

```bash
python -m agents.farmer_agent --name "Green Valley" --registry <REGISTRY_ADDRESS>
```

By default this uses simulated Stripe onboarding and creates a demo connected account id like `acct_demo_green_valley`. Real Stripe Express onboarding is gated separately from transfers:

```env
STRIPE_CONNECT_ONBOARDING_ENABLED=false
STRIPE_CONNECT_TRANSFERS_ENABLED=false
```

Set `STRIPE_CONNECT_ONBOARDING_ENABLED=true` only when using a Stripe test key and you want a real hosted onboarding link. A future web form can reuse `agents/onboarding.py`; the current MVP prints the run command instead of launching and supervising farmer processes.

## Current Demo Data

| Seller | Stock | Unit Price | Notes |
|---|---:|---:|---|
| Farm A | 200 | $0.40 | Cheapest but limited stock. |
| Farm B | 400 | $0.45 | Main filler seller. |
| Farm C | 100 | $0.50 | Backup supplier. |
| Sunny Acres | 300 | $0.48 | Flockx Business Agent target with code fallback. |
| Green Valley | 300 | $0.42 | Self-onboarded seller with simulated Stripe account. |

For `500 tomatoes`, the optimizer picks Farm A first and then Green Valley.

## Running uAgents Locally

The structured uAgent files are ready for the next integration step:

```bash
python scripts/run_local_bureau.py
```

That starts the registry plus all configured farm agents in one local uAgents Bureau. To run individual agents instead:

```bash
python -m agents.registry_agent
python -m agents.farmer_agent --name "Farm A"
python -m agents.farmer_agent --name "Farm B"
python -m agents.farmer_agent --name "Farm C"
python -m agents.orchestrator_agent
python -m agents.asi_chat_agent
```

Before live use, replace demo seeds in `config/farms.json` and `.env` with real secret values. Do not commit real seeds or API keys.

The orchestrator currently exposes a structured `ProcurementRequest` message. The ASI:One Chat Protocol adapter should call the same workflow core after the current hosted Chat Protocol setup is confirmed.

## Environment

Copy the example file:

```bash
cp .env.example .env
```

Important values:

- `ASI_ONE_API_KEY`: enables ASI:One intent parsing.
- `ASI_ONE_BASE_URL`: ASI:One chat completions endpoint.
- `ASI_ONE_MODEL`: model name used for intent extraction.
- `AGRIBROKER_INTENT_MODE`: `local`, `asi`, or `auto`.
- `AGRIBROKER_DISCOVERY_MODE`: `local` uses `config/farms.json`; `agent` asks a live Registry agent.
- `AGRIBROKER_REGISTRY_ADDRESS`: Registry agent address used when `AGRIBROKER_DISCOVERY_MODE=agent`.
- `AGRIBROKER_BUYER_PAYMENT_MODE`: `simulated` or `stripe`.
- `STRIPE_SECRET_KEY`: Stripe secret key for Checkout Sessions and Connect transfers.
- `STRIPE_SUCCESS_URL` / `STRIPE_CANCEL_URL`: redirect URLs for Checkout.
- `AGRIBROKER_FARM_PAYMENT_MODE`: `simulated`, `testnet`, or `stripe_connect`.
- `STRIPE_CONNECT_TRANSFERS_ENABLED`: `true` to allow real Stripe Connect farm payouts (default `false` keeps them simulated).
- `FETCH_NETWORK`: `testnet` for this hackathon demo.
- `FETCH_EXPLORER_TX_URL`: base URL used when real tx hashes are present.
- Agent seeds: replace demo seeds before deployment.

## Agent Discovery Mode

The ASI chat agent defaults to local discovery so the judge-facing demo stays reliable:

```env
AGRIBROKER_DISCOVERY_MODE=local
```

When the Registry and Farmer agents are running, switch to live agent discovery:

```env
AGRIBROKER_DISCOVERY_MODE=agent
AGRIBROKER_REGISTRY_ADDRESS=<registry agent address>
```

In agent mode, farmers register themselves with the Registry. The orchestrator asks the Registry who sells tomatoes, sends `QuoteRequest` messages to those farm addresses, collects `QuoteResponse` messages, sends purchase orders, pays invoices, and waits for receipts.

To test live agent discovery locally:

1. In terminal 1, start the Registry plus all farm agents:

```bash
python scripts/run_local_bureau.py
```

2. Copy the printed `Registry: agent1...` address.
3. In terminal 2, export:

```bash
export AGRIBROKER_DISCOVERY_MODE=agent
export AGRIBROKER_REGISTRY_ADDRESS=<registry agent address>
python -m agents.asi_chat_agent
```

4. In ASI:One, ask:

```text
I need 500 tomatoes under $250.
```

If anything goes sideways during live judging, switch back to:

```bash
export AGRIBROKER_DISCOVERY_MODE=local
```

## Agentverse Profile Files

Agentverse README/profile text lives in:

- `docs/agentverse-profile.md`: buyer-facing AgriBroker chat agent.
- `docs/agentverse/registry.md`: seller discovery registry.
- `docs/agentverse/orchestrator.md`: structured procurement orchestrator.
- `docs/agentverse/farm-a.md`, `farm-b.md`, `farm-c.md`: seeded farm agents.
- `docs/agentverse/sunny-acres.md`: verified storefront candidate and Business Agent bridge.
- `docs/agentverse/green-valley.md`: self-onboarded seller.
- `docs/agentverse/setup.md`: launch and mailbox checklist.

## Build Roadmap

1. Local deterministic demo with simulated payment. Done.
2. Structured local uAgent quote and invoice flow. Started; local Bureau runner added.
3. ASI:One Chat Protocol entry point. Added.
4. ASI:One intent parsing. Local fallback added; live API key path available.
5. Stripe buyer funding. Checkout Session path added; real key/webhook confirmation still optional.
6. Testnet FET farm payouts. Farm payout mode and fake-ledger tests added; live funding still needs wallet setup.
7. Agentverse deployment.
8. Flockx Business Agent participation or verified storefront fallback.

## Manual Test Prompts

Use these after every major change:

```text
I need 500 tomatoes under $250.
```

Expected: confirmed $206 plan with Farm A and Green Valley paid.

```text
I need 1500 tomatoes under $1000.
```

Expected: partial plan with a 200 tomato shortfall and no payment executed.

```text
I need 500 tomatoes under $100.
```

Expected: over-budget result and no payment executed.

## Judge Story

AgriBroker is built to show "intent to action":

- The buyer states an intent.
- Agents autonomously discover and compete.
- The orchestrator chooses the cheapest feasible allocation.
- Funds move through the agent network.
- The buyer receives a transparent receipt.

The key differentiator is that the multi-agent architecture is necessary: the order cannot be optimally fulfilled by blindly calling one API or one seller.
