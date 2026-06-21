# Devpost Summary Draft

## One-Liner

AgriBroker is an autonomous produce procurement network where ASI:One turns a buyer request into multi-agent quote discovery, split-order optimization, and simulated Stripe Checkout/Connect payments.

## Problem

Bulk produce buyers often need to compare multiple suppliers, check available stock, split orders, stay under budget, and send payments to several sellers. That process is manual, slow, and error-prone.

## Solution

AgriBroker lets a buyer ask:

```text
I need 500 tomatoes under $250.
```

The orchestrator agent discovers seller agents, collects tomato quotes, computes the cheapest allocation, funds the order through the orchestrator, pays selected farms, and returns one combined receipt.

## Fetch.ai Stack

- ASI:One: buyer-facing natural language entry point.
- uAgents: orchestrator, registry, and farm agents.
- Agentverse: mailbox, discovery, and hosted agent profile.
- Chat Protocol: ASI:One-compatible conversation interface.
- Stripe payments: simulated Checkout buyer funding and simulated Connect farm payouts.
- Flockx Business Agent: Sunny Acres verified seller target or storefront fallback.

## Why Multi-Agent Matters

The demo is not one API call. Farm A is cheapest but has limited stock. Farm B has enough to complete the order but costs more. AgriBroker must coordinate across sellers to produce the cheapest feasible split.

Expected demo result:

- Farm A: 200 tomatoes = $80
- Green Valley: 300 tomatoes = $126
- Total: $206
- Budget remaining: $44

## Future Work

- Real buyer wallet funding inside ASI:One.
- Fully verified Flockx seller participation in the quote round.
- Delivery windows and logistics optimization.
- Seller reputation and quality scoring.
- Optional negotiation round before final purchase.
