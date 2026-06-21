# AgriBroker Farmer Agent

This is a reusable profile for self-onboarded AgriBroker farm agents.

Each farmer agent owns a catalog, responds to quote requests, invoices accepted purchase orders, and confirms simulated Stripe Connect payouts.

## Role

- Advertise produce inventory to the Registry.
- Quote available stock and unit price.
- Issue an invoice with a wallet address and Stripe connected account id.
- Confirm payment and reserve inventory after settlement.

## Protocol Messages

- `QuoteRequest`
- `QuoteResponse`
- `PurchaseOrder`
- `Invoice`
- `PaymentSent`
- `Receipt`

## Demo Safety

Stripe account ids may be simulated with `acct_demo_<farm_slug>`. Real transfers are disabled unless `STRIPE_CONNECT_TRANSFERS_ENABLED=true` and a real Stripe test key is configured.
