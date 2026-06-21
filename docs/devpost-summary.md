# AgriBroker Devpost Draft

## Project Name

AgriBroker

## Tagline

Autonomous produce procurement where ASI:One turns a buyer request into live farm quotes, optimized split orders, Stripe checkout, and agent receipts.

## One-Liner

AgriBroker is a multi-agent marketplace for produce: a buyer asks for tomatoes in ASI:One, the orchestrator discovers farm agents, compares inventory and prices, chooses the cheapest split, funds the order through Stripe Checkout, pays selected farms, and returns one combined receipt.

## Short Description

AgriBroker lets buyers source produce through autonomous agents instead of manually calling farms, comparing prices, splitting orders, and coordinating payments. A buyer can type:

```text
I need 500 tomatoes under $250.
```

AgriBroker parses that request, asks registered farm agents for live inventory and unit prices, runs an optimizer, creates a Stripe Checkout funding step, sends purchase orders to the winning farms, simulates or executes farm payouts, decrements inventory, and returns a transparent receipt.

The demo uses tomatoes because the split-order problem is easy to see: Farm A is cheapest but has limited stock, Green Valley is newly self-onboarded and competitive, and Sunny Acres represents a Fetch Business Agent storefront with a code-backed fallback for reliability.

## Inspiration

Produce procurement is still surprisingly manual. A restaurant, food co-op, or community buyer may need to know which farms have inventory today, who is cheapest, whether one farm can fill the whole order, how to split across suppliers, and how to pay each seller. That is exactly the kind of coordination problem agents should handle.

We wanted to build a demo where the multi-agent architecture is not decorative. Multiple sellers matter because no single supplier may have the best combination of stock and price. The orchestrator has a real job: discover sellers, collect quotes, optimize, pay, and produce an auditable receipt.

## What It Does

AgriBroker performs an end-to-end procurement workflow:

1. The buyer chats with AgriBroker in ASI:One.
2. AgriBroker parses item, quantity, and budget.
3. In live agent mode, it asks the Registry agent who sells the requested item.
4. The Registry returns farm agent addresses.
5. The orchestrator sends `QuoteRequest` messages to each farm.
6. Farm agents answer with inventory and unit prices.
7. The optimizer computes the cheapest feasible split across sellers.
8. The buyer funds the order through Stripe Checkout.
9. After confirmation, AgriBroker sends purchase orders to the winning farms.
10. Farm agents invoice the orchestrator.
11. The payment layer records Stripe Connect-style simulated payouts, with a guarded path for real Connect transfers.
12. Farms confirm receipts and reserve/decrement inventory.
13. AgriBroker returns a final receipt with the optimized allocation, total, payment status, and an agent trace.

## Demo Scenario

Prompt:

```text
I need 500 tomatoes under $250.
```

Seed seller data:

| Seller | Stock | Unit Price | Role |
|---|---:|---:|---|
| Farm A | 200 | $0.40 | Cheapest but limited stock |
| Farm B | 400 | $0.45 | Reliable mid-size supplier |
| Farm C | 100 | $0.50 | Premium backup supplier |
| Sunny Acres | 300 | $0.48 | Fetch Business Agent storefront with code fallback |
| Green Valley | 300 | $0.42 | Self-onboarded competitive seller |

Expected optimized result:

| Seller | Quantity | Cost |
|---|---:|---:|
| Farm A | 200 | $80 |
| Green Valley | 300 | $126 |
| Total | 500 | $206 |

The optimizer matters because Farm A is cheapest but cannot satisfy the full order. AgriBroker automatically splits the order and stays under budget.

## Key Features

- **ASI:One chat entry point:** Buyer starts from natural language.
- **Agentverse-ready uAgents:** AgriBroker, Registry, structured orchestrator, and each farm agent publish profile metadata and README text.
- **Live agent discovery mode:** The orchestrator asks a Registry agent for seller addresses, sends live `QuoteRequest` messages to farmer agents, then sends `PurchaseOrder`, `PaymentSent`, and receives `Receipt` messages.
- **Agent trace in the receipt:** ASI:One output can show `Registry returned...`, `Sent QuoteRequest...`, and `Sent PurchaseOrder...` so judges can see real agent coordination.
- **Pure optimizer:** A deterministic cheapest-split optimizer handles limited stock, budget constraints, shortfalls, and over-budget cases.
- **Stripe buyer funding:** With a test Stripe key, AgriBroker creates a real Stripe Checkout link for buyer payment.
- **Payment-safe architecture:** Farm payouts default to simulated Stripe Connect so the demo cannot accidentally move real money. Real Connect transfers are explicitly gated by `STRIPE_CONNECT_TRANSFERS_ENABLED=true`.
- **Post-checkout confirmation:** Buyer returns to ASI:One and sends `confirm order <order-id>`; AgriBroker verifies Checkout status and then releases farm payout/receipt steps.
- **Farmer self-onboarding:** `scripts/onboard_farmer.py` appends a new farm to `config/farms.json`, validates the config, creates a simulated connected account, and prints the run command for that farmer agent.
- **Fetch Business Agent bridge:** Sunny Acres can be represented as a no-code Fetch/Flockx Business Agent. If a Business Agent address is configured, AgriBroker asks it for a live natural-language quote over Chat Protocol, parses the reply, and overlays it into the optimizer. If it times out, the seeded Sunny Acres catalog keeps the demo reliable.

## How We Built It

The system is organized around a small set of agent roles:

- **AgriBroker ASI chat agent:** `agents/asi_chat_agent.py`
  Handles Chat Protocol messages from ASI:One, sends progress updates, coordinates local or live agent workflows, asks the Sunny Acres Business Agent for optional live quotes, and formats the final receipt.

- **Registry agent:** `agents/registry_agent.py`
  Maintains a catalog of which farm agents sell which items.

- **Farmer agents:** `agents/farmer_agent.py`
  Each farm holds inventory and price data, responds to quote requests, issues invoices, confirms payment, and reserves inventory.

- **Agent network workflow:** `agents/agent_network.py`
  Implements the live message loop between orchestrator, Registry, and farmer agents.

- **Local workflow:** `agents/workflow.py`
  Provides a deterministic fallback path with the same optimizer/payment behavior, useful for tests and demo reliability.

- **Optimizer:** `agents/optimizer.py`
  Sorts quotes by unit price and fills the order greedily, which is optimal for per-unit pricing with no fixed shipping costs.

- **Payments:** `agents/payments.py`
  Supports simulated buyer funding, Stripe Checkout, simulated Stripe Connect transfers, guarded real Connect transfer calls, and optional Fetch testnet payment helpers.

- **Onboarding:** `agents/onboarding.py` and `scripts/onboard_farmer.py`
  Allow new sellers to join without manually editing JSON.

## Fetch / ASI Stack Used

- **ASI:One:** Natural-language buyer interface.
- **Agentverse:** Agent profiles, mailbox connection, and discoverability.
- **uAgents:** Code agents for AgriBroker, Registry, and farms.
- **Chat Protocol:** ASI:One-compatible chat interface and optional Business Agent quote path.
- **Flockx / Fetch Business Agent:** Sunny Acres verified storefront path with code-backed fallback.
- **Fetch testnet support:** Payment layer includes optional Fetch testnet transfer helpers, although the current reliable demo uses Stripe Checkout and simulated Connect payouts.

## Stripe Stack Used

- **Stripe Checkout:** Buyer funding flow.
- **Stripe test mode:** Use test card `4242 4242 4242 4242`.
- **Stripe Connect model:** The orchestrator acts like the platform; farms have connected-account ids. For the demo, transfers are simulated unless explicitly enabled.

## What Makes It Multi-Agent

AgriBroker is not just an LLM wrapper. In live agent mode:

- Farmers register with a Registry.
- The orchestrator asks the Registry for sellers.
- The orchestrator sends quote requests to each seller agent.
- Each farm agent independently returns stock and pricing.
- The optimizer chooses winners.
- The orchestrator sends purchase orders only to selected farms.
- Farms invoice and acknowledge payment.

The ASI receipt includes an `Agent trace` section so the agent-to-agent communication is visible in the demo.

## Farmer Onboarding Demo

AgriBroker can onboard a new farmer from the command line:

```bash
python scripts/onboard_farmer.py \
  --name "Blue Ridge Farm" \
  --item tomatoes \
  --stock 250 \
  --price 0.43 \
  --floor 0.39 \
  --no-stripe
```

The script:

- chooses the next available port,
- generates a farm seed,
- creates a simulated Stripe connected account id,
- validates the full config,
- appends the farm to `config/farms.json`,
- prints the command to run that farmer as an agent.

This shows how a new seller can join the marketplace without changing the orchestrator.

## Challenges

- **Reliability vs. live integrations:** ASI:One, Agentverse mailbox, Business Agents, Stripe, and uAgent networking all introduce external moving parts. We kept a deterministic local path and added live integrations as adapters around the core workflow.
- **Stripe confirmation flow:** A completed Stripe Checkout session no longer has a Checkout URL, so the system needed a two-step flow: create Checkout, wait for the buyer, then confirm order by checking the session status.
- **Making agent coordination visible:** Terminal logs are useful for developers but not judges. We added ASI-visible progress messages and an `Agent trace` section.
- **Business Agent boundary:** Fetch Business Agents are conversational, so we added a natural-language quote parser and a fallback catalog mirror to keep the optimizer stable.
- **Avoiding accidental real money movement:** Stripe Connect transfers are explicitly disabled unless a developer opts in with both real connected accounts and `STRIPE_CONNECT_TRANSFERS_ENABLED=true`.

## Accomplishments

- Built an end-to-end procurement flow from ASI:One prompt to optimized receipt.
- Implemented live Registry/Farmer agent discovery and quote messaging.
- Added visible agent traces so the multi-agent behavior is judge-readable.
- Integrated Stripe Checkout for buyer funding.
- Added a safe Stripe Connect-style seller payout path.
- Built a farmer self-onboarding script.
- Added a Sunny Acres Business Agent bridge with natural-language quote parsing and fallback behavior.
- Wrote a broad test suite covering optimizer behavior, workflow cases, payments, onboarding, Business Agent parsing, and agent-network messaging.

## What We Learned

The hardest part of agentic commerce is not just making agents talk. It is making the system reliable, inspectable, and honest about what happened. A good demo needs graceful fallbacks, clear receipts, and visible traces. The optimizer and protocol models kept the project grounded while ASI:One, Agentverse, Business Agents, and Stripe added richer interaction surfaces.

## What's Next

- Host the Registry, farms, and AgriBroker agents so the laptop does not need to stay running.
- Replace simulated Stripe Connect ids with real test connected accounts.
- Add webhooks for automatic Stripe Checkout confirmation.
- Add seller reputation, delivery windows, and quality scoring.
- Add negotiation rounds before purchase.
- Expand beyond tomatoes into mixed produce baskets.
- Make Business Agent onboarding fully self-serve for non-technical farms.

## Demo Video Outline

1. Show the problem: buyer needs 500 tomatoes and should not manually compare farms.
2. Show Agentverse profiles for AgriBroker and supporting farm agents.
3. Show optional Sunny Acres Business Agent storefront.
4. Ask AgriBroker in ASI:One: `I need 500 tomatoes under $250.`
5. Show progress messages and quotes.
6. Show optimized split: Farm A + Green Valley.
7. Open Stripe Checkout and pay with a test card.
8. Return to ASI:One and send `confirm order <order-id>`.
9. Show final receipt and agent trace.
10. Show farmer onboarding command for a new seller.

## Links To Include

- GitHub repo: `<repo URL>`
- Demo video: `<video URL>`
- AgriBroker Agentverse profile: `<profile URL>`
- Sunny Acres Business Agent profile: `<profile URL if available>`
- ASI:One chat link: `<chat URL if available>`
