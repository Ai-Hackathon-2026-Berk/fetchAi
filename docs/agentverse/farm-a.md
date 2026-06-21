# Farm A

Farm A is the lowest-cost tomato supplier in the AgriBroker demo.

## Catalog

- Item: tomatoes
- Stock: 200
- Unit price: $0.40
- Stripe account: `acct_demo_farm_a`

## Role

Farm A responds to quote requests, invoices accepted purchase orders, and confirms receipt after the orchestrator sends a simulated Stripe Connect payout.

## Demo Behavior

Farm A is intentionally cheap but stock-limited. For the standard request:

```text
I need 500 tomatoes under $250.
```

Farm A supplies its full 200 tomato inventory, and the optimizer fills the remaining quantity from another seller.

## Protocol Messages

- Receives `QuoteRequest`
- Sends `QuoteResponse`
- Receives `PurchaseOrder`
- Sends `Invoice`
- Receives `PaymentSent`
- Sends `Receipt`
