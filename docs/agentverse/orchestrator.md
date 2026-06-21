# AgriBroker Orchestrator

The AgriBroker Orchestrator coordinates structured procurement requests across the marketplace.

For ASI:One chat, judges should use the main AgriBroker chat agent. This structured orchestrator exists to show the underlying agent-to-agent workflow: buyer request, seller discovery, quote collection, optimization, simulated Stripe settlement, and receipt return.

## Role

- Parses procurement requests through the shared workflow core.
- Discovers sellers through the Registry when live discovery is enabled.
- Requests quotes from farm agents.
- Computes the cheapest split order.
- Coordinates simulated Stripe Checkout and Connect-style payouts.
- Returns a structured procurement result.

## Current Demo

Prompt:

```text
I need 500 tomatoes under $250.
```

Expected result:

- Farm A: 200 tomatoes at $0.40
- Green Valley: 300 tomatoes at $0.42
- Total: $206.00
- Buyer payment: Stripe Checkout (simulated)
- Farm payout mode: Stripe Connect (simulated)

## Protocol Messages

- `ProcurementRequest`
- `ProcurementResult`
- `WhoSells`
- `QuoteRequest`
- `PurchaseOrder`
- `PaymentSent`
- `Receipt`

## Positioning

The orchestrator is a neutral buyer-side agent. It does not charge a broker fee in this MVP; it optimizes for price and reliable fulfillment.
