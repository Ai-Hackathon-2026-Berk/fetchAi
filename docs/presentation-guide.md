# AgriBroker Presentation Guide

This guide is written for a 3-5 minute hackathon presentation. Use the slide titles as deck headings and the speaker notes as your narration.

## Core Pitch

AgriBroker is an autonomous procurement marketplace for produce. A buyer types one request into ASI:One, and AgriBroker coordinates multiple seller agents to discover inventory, compare prices, optimize a split order, route buyer funding through Stripe Checkout, and return one receipt.

The key sentence:

```text
AgriBroker turns "I need 500 tomatoes under $250" into live agent discovery, optimized farm selection, payment coordination, and a receipt.
```

## Slide 1: Title

**AgriBroker**

Autonomous produce procurement for ASI:One, Agentverse, and farm seller agents.

Speaker notes:

> AgriBroker is a multi-agent produce procurement marketplace. Instead of a buyer manually calling farms, comparing prices, splitting orders, and coordinating payment, the buyer sends one natural-language request to ASI:One and the agents do the work.

## Slide 2: Problem

**Produce Procurement Is Still Manual**

- Buyers need to compare farm inventory and prices.
- One farm may not have enough stock.
- The cheapest farm may sell out quickly.
- Orders often need to be split across suppliers.
- Payments and receipts are fragmented.

Speaker notes:

> The pain point is coordination. A restaurant, co-op, or bulk buyer may know what they want, but not which seller has enough stock, who is cheapest, or how to split the order. This is a natural fit for agents because each seller can expose its own inventory and pricing, and a buyer-facing orchestrator can optimize across them.

## Slide 3: Solution

**One Buyer Request, Many Agent Actions**

Buyer prompt:

```text
I need 500 tomatoes under $250.
```

AgriBroker:

- parses item, quantity, and budget,
- discovers seller agents,
- asks farms for live quotes,
- computes the cheapest split,
- creates Stripe Checkout,
- confirms payment,
- sends purchase orders,
- returns one receipt.

Speaker notes:

> The important thing is that this is not just a chatbot returning text. The orchestrator contacts other agents, gathers structured quotes, runs an optimizer, and then coordinates payment and receipts.

## Slide 4: Architecture

**Agent Network**

```text
ASI:One buyer
    |
AgriBroker Chat Agent
    |
Registry Agent ------ Farmer Agents
    |                   |
    |                   Farm A
    |                   Farm B
    |                   Farm C
    |                   Sunny Acres
    |                   Green Valley
    |
Optimizer + Payments
```

Components:

- AgriBroker ASI chat agent
- Registry uAgent
- Farmer uAgents
- Sunny Acres Business Agent bridge
- Stripe Checkout / Connect-style payment layer
- Cheapest-split optimizer

Speaker notes:

> The Registry tells AgriBroker who sells tomatoes. AgriBroker asks each farm for inventory and price. The optimizer chooses the allocation. Then the orchestrator coordinates Checkout and farm payouts.

## Slide 5: Demo Data

**Tomato Marketplace**

| Seller | Stock | Price | Notes |
|---|---:|---:|---|
| Farm A | 200 | $0.40 | Cheapest, limited stock |
| Green Valley | 300 | $0.42 | Self-onboarded seller |
| Farm B | 400 | $0.45 | Reliable filler |
| Sunny Acres | 300 | $0.48 | Business Agent storefront |
| Farm C | 100 | $0.50 | Premium backup |

Expected result:

```text
Farm A: 200 tomatoes = $80
Green Valley: 300 tomatoes = $126
Total: $206
Budget: $250
```

Speaker notes:

> This setup makes the optimizer meaningful. Farm A is cheapest but can only provide 200. Green Valley is next cheapest and fills the remaining 300. The result is cheaper than buying from one larger supplier.

## Slide 6: What Is Live

**Implemented Features**

- ASI:One Chat Protocol agent.
- Agentverse profile metadata and README files.
- Live Registry/Farmer agent mode.
- Local fallback mode for reliable demos.
- Agent trace in chat output.
- Stripe Checkout buyer funding.
- Confirm-order flow after Checkout.
- Simulated Stripe Connect farm payouts.
- Farmer self-onboarding.
- Sunny Acres Business Agent live quote adapter with fallback.
- Test suite covering optimizer, payments, onboarding, Business Agent parsing, and agent-network flow.

Speaker notes:

> The system has a reliable local path and a live agent path. In live mode, the orchestrator actually sends messages to the Registry and farmer agents. The receipt includes an agent trace so judges can see that coordination.

## Slide 7: Live Demo Script

**Demo Flow**

1. Show ASI:One chat with AgriBroker.
2. Ask:

   ```text
   I need 500 tomatoes under $250.
   ```

3. Show progress:
   - discovering farms,
   - collecting quotes,
   - optimizing split.
4. Open Stripe Checkout.
5. Pay with test card:

   ```text
   4242 4242 4242 4242
   ```

6. Return to ASI:One:

   ```text
   confirm order order-...
   ```

7. Show final receipt and `Agent trace`.

Speaker notes:

> The key proof moments are the quote list, the optimized split, the Checkout link, the final confirmation, and the agent trace.

## Slide 8: Agent Trace

**Proof Of Agent-To-Agent Work**

Expected ASI output includes:

```text
Agent trace:
- Registry returned 5 seller addresses.
- Sent QuoteRequest to farm agent ...
- Sent PurchaseOrder to Farm A agent at ...
- Done: 500 tomatoes sourced ... through live agent messages.
```

Speaker notes:

> This trace is there for judges. It shows that AgriBroker is not hardcoding the answer; it is coordinating with supporting agents.

## Slide 9: Farmer Onboarding

**New Sellers Can Join**

Command:

```bash
python scripts/onboard_farmer.py \
  --name "Blue Ridge Farm" \
  --item tomatoes \
  --stock 250 \
  --price 0.43 \
  --floor 0.39 \
  --no-stripe
```

What happens:

- validates input,
- picks an available port,
- creates a farm seed,
- creates a simulated connected account,
- updates `config/farms.json`,
- prints the farmer agent run command.

Speaker notes:

> This demonstrates marketplace extensibility. The orchestrator does not need to know about a new farm in advance. Once the farm is onboarded and registered, it can participate in discovery and quoting.

## Slide 10: Fetch Business Agent

**Sunny Acres Verified Storefront**

Sunny Acres has two roles:

- Business Agent storefront for no-code seller presence.
- Code-backed farm mirror for reliable optimization and settlement.

Implemented bridge:

- AgriBroker can message the Business Agent over Chat Protocol.
- It asks for a natural-language quote.
- It parses the reply into a structured `Quote`.
- It overlays that quote onto Sunny Acres in the optimizer.
- If the Business Agent is slow or unparseable, the seeded catalog price is used.

Speaker notes:

> This is how we bridge no-code business presence with structured agent commerce. Non-technical farms can have a Business Agent storefront, while the orchestrator still gets a reliable quote for optimization.

## Slide 11: Payments

**Stripe Checkout With Safe Farm Payouts**

Buyer side:

- Stripe Checkout Session created with a test key.
- Buyer pays in a hosted Stripe page.
- Buyer returns to ASI:One and confirms the order.

Farm side:

- Stripe Connect-style payouts are simulated by default.
- Real Connect transfers are gated by:

```env
STRIPE_CONNECT_TRANSFERS_ENABLED=true
```

Speaker notes:

> We use real Stripe Checkout for the buyer experience, but keep farm payouts simulated unless explicitly enabled. That prevents accidental real money movement during a hackathon while preserving the marketplace payment model.

## Slide 12: Why It Matters

**Intent To Action**

AgriBroker proves:

- natural-language buyer intent,
- autonomous seller discovery,
- live quote gathering,
- optimization across suppliers,
- payment coordination,
- auditable receipts.

Speaker notes:

> The project matters because it turns a buyer's intent into action across a network. The multi-agent setup is necessary because inventory, price, and availability live with different sellers.

## Slide 13: Challenges

**Hard Parts**

- Keeping ASI:One, Agentverse, uAgents, Business Agents, and Stripe reliable at once.
- Designing honest fallbacks.
- Making payment confirmation two-step instead of pretending Checkout is instant.
- Making agent-to-agent work visible to judges.
- Parsing conversational Business Agent replies safely.

Speaker notes:

> The biggest engineering choice was to protect the demo with a deterministic core while layering live integrations as adapters. That gave us something stable and still allowed real ecosystem touchpoints.

## Slide 14: Next Steps

**Roadmap**

- Hosted deployment for all agents.
- Stripe webhooks for automatic confirmation.
- Real test connected accounts for farm payouts.
- Delivery windows and logistics optimization.
- Seller reputation and quality scoring.
- More produce types and mixed baskets.
- Fully self-serve Business Agent seller onboarding.

Speaker notes:

> The next version moves from demo marketplace to real procurement platform: hosted agents, automated payment confirmation, logistics, reputation, and broader catalogs.

## Live Demo Checklist

Before presenting:

```bash
python -m pytest
python scripts/check_demo_ready.py
python scripts/check_stripe_ready.py
```

Run:

```bash
python scripts/serve_checkout_pages.py
python -m agents.registry_agent
python -m agents.farmer_agent --name "Farm A" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Farm B" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Farm C" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Sunny Acres" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Green Valley" --registry <REGISTRY_ADDRESS>
python -m agents.asi_chat_agent
```

Set:

```env
AGRIBROKER_DISCOVERY_MODE=agent
AGRIBROKER_REGISTRY_ADDRESS=<REGISTRY_ADDRESS>
AGRIBROKER_BUYER_PAYMENT_MODE=stripe
AGRIBROKER_FARM_PAYMENT_MODE=stripe_connect
STRIPE_CONNECT_TRANSFERS_ENABLED=false
```

Optional Business Agent:

```env
AGRIBROKER_BUSINESS_SELLER_ADDRESS=<Sunny Acres Business Agent address>
AGRIBROKER_BUSINESS_SELLER_NAME=Sunny Acres
```

## Backup Demo Path

If live agent networking or Business Agent messaging fails:

```env
AGRIBROKER_DISCOVERY_MODE=local
AGRIBROKER_BUSINESS_SELLER_ADDRESS=
```

Then run:

```bash
python -m agents.asi_chat_agent
```

Narration:

> The local mode uses the same optimizer, payment, and receipt logic with seeded farm states. It is our reliable fallback for demo conditions.

## Likely Judge Questions

### Is this actually multi-agent?

Yes. In agent discovery mode, AgriBroker asks the Registry for seller addresses, sends `QuoteRequest` messages to farm agents, then sends purchase orders and payment notifications to the selected farms. The receipt includes an `Agent trace` showing those steps.

### Is Stripe real?

Buyer Checkout can be real in Stripe test mode when `STRIPE_SECRET_KEY` is set. Farm payouts are simulated by default for safety, but the code includes guarded Stripe Connect transfer support that only runs when explicitly enabled.

### What is the Fetch Business Agent doing?

Sunny Acres is the Business Agent storefront path. AgriBroker can send it a Chat Protocol quote request, parse the natural-language response, and overlay that live quote into the optimizer. A code-backed Sunny Acres farm remains as fallback so the live demo does not break.

### Why not just use one database?

The agent model matters because sellers own their own inventory, pricing, identity, and receipts. The orchestrator does not need to own every seller's backend; it coordinates among agents.

### What is the business model?

The current MVP is a neutral broker with no fee. Future versions could add a broker fee, subscription for sellers, or buyer-side procurement automation pricing.

