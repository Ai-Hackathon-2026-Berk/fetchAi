# AgriBroker

Autonomous produce procurement for the Fetch.ai ecosystem.

AgriBroker lets a buyer ask for produce in natural language, then uses agents to discover sellers, gather quotes, compute the cheapest split, fund the order, pay selected farms, and return a single itemized receipt.

Demo prompt:

```text
I need 500 tomatoes under 250 FET.
```

Expected result:

- Farm A supplies 200 tomatoes at 0.40 FET each.
- Farm B supplies 300 tomatoes at 0.45 FET each.
- Total cost is 215 FET.
- The buyer stays under the 250 FET budget.

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
| Payment layer | Buyer funds orchestrator; orchestrator pays selected farms. Uses simulated mode locally and testnet FET when live. |

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

## ASI:One And Agentverse

The ASI:One entry point is:

```bash
python -m agents.asi_chat_agent
```

This starts a Chat Protocol-compatible uAgent with `mailbox=True` and `publish_agent_details=True`. Keep this process running while testing from ASI:One.

Setup steps:

1. Create `.env` from `.env.example` if needed.
2. Add `ASI_ONE_API_KEY` when you want live ASI:One intent parsing.
3. Keep `AGRIBROKER_PAYMENT_MODE=simulated` for the first ASI:One test.
4. Run `python -m agents.asi_chat_agent`.
5. Open the Agent Inspector URL printed in the terminal.
6. Click **Connect** and choose **Mailbox**.
7. Open the Agent Profile in Agentverse.
8. Set the public profile:
   - Name: `AgriBroker`
   - Handle: `@agribroker`
   - Description: `Autonomous produce procurement agent that discovers farms, compares tomato quotes, optimizes split orders, and returns payment receipts.`
   - Tags: `procurement`, `produce`, `marketplace`, `payments`, `Fetch.ai`
9. Click **Chat with Agent** from Agentverse.
10. Send:

```text
I need 500 tomatoes under 250 FET.
```

Expected ASI:One response:

```text
AgriBroker found 4 sellers for tomatoes.

Quotes:
Farm A: 200 @ 0.40 FET
Farm B: 400 @ 0.45 FET
Farm C: 100 @ 0.50 FET
Sunny Acres: 300 @ 0.48 FET

Optimal split:
Farm A: 200 tomatoes = 80.00 FET
Farm B: 300 tomatoes = 135.00 FET

Total: 215.00 FET
Budget: 250.00 FET
Status: confirmed
Payment mode: simulated/local demo
```

Troubleshooting:

- If the agent cannot bind to `0.0.0.0:8200`, run it from a normal terminal instead of a restricted sandbox, or change `ORCHESTRATOR_PORT`.
- If Agentverse mailbox logs show `CERTIFICATE_VERIFY_FAILED`, fix local Python certificates. On macOS python.org installs, run `/Applications/Python 3.13/Install Certificates.command` if present. You can also run:

```bash
export SSL_CERT_FILE="$(python3 -c 'import certifi; print(certifi.where())')"
python -m agents.asi_chat_agent
```

## Payment Model

The intended marketplace payment flow is:

1. Buyer approves the optimized plan.
2. Buyer pays the orchestrator wallet for the order total.
3. Orchestrator acts as a neutral purchasing agent for that order.
4. Orchestrator pays each winning farm.
5. Farms confirm payment, decrement inventory, and return receipts.
6. Orchestrator returns one combined buyer receipt.

For local development, payments are simulated and clearly labeled with `simulated-*` transaction ids. For the hackathon demo, the safest live version is to pre-fund the orchestrator or a demo buyer wallet with testnet FET, then show the orchestrator paying farms on-chain. If the network or faucet fails during judging, the fallback receipt keeps the workflow alive while making the simulated status explicit.

## Current Demo Data

| Seller | Stock | Unit Price | Notes |
|---|---:|---:|---|
| Farm A | 200 | 0.40 FET | Cheapest but limited stock. |
| Farm B | 400 | 0.45 FET | Main filler seller. |
| Farm C | 100 | 0.50 FET | Backup supplier. |
| Sunny Acres | 300 | 0.48 FET | Flockx Business Agent target with code fallback. |

For `500 tomatoes`, the optimizer picks Farm A first and then Farm B.

## Running uAgents Locally

The structured uAgent files are ready for the next integration step:

```bash
python -m agents.registry_agent
python -m agents.farmer_agent
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
- `AGRIBROKER_PAYMENT_MODE`: `simulated` or `testnet`.
- Agent seeds: replace demo seeds before deployment.

## Build Roadmap

1. Local deterministic demo with simulated payment. Done.
2. Structured local uAgent quote and invoice flow. Started.
3. ASI:One Chat Protocol entry point. Added.
4. ASI:One intent parsing.
5. Testnet FET payment from orchestrator to farms.
6. Agentverse deployment.
7. Flockx Business Agent participation or verified storefront fallback.

## Manual Test Prompts

Use these after every major change:

```text
I need 500 tomatoes under 250 FET.
```

Expected: confirmed 215 FET plan with Farm A and Farm B paid.

```text
I need 1200 tomatoes under 1000 FET.
```

Expected: partial plan with a 200 tomato shortfall and no payment executed.

```text
I need 500 tomatoes under 100 FET.
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
