# Farm B

Farm B is a reliable mid-size tomato supplier in the AgriBroker marketplace.

## Catalog

- Item: tomatoes
- Stock: 400
- Unit price: $0.45
- Stripe account: `acct_demo_farm_b`

## Role

Farm B provides backup tomato supply when lower-cost farms cannot satisfy the full order. It participates in quote discovery, invoicing, and simulated Stripe Connect settlement.

## Demo Behavior

Farm B used to fill the main demo order before Green Valley onboarded. After Green Valley joins at $0.42, Farm B remains a reliable fallback supplier for larger orders or when cheaper farms run out.

## Protocol Messages

- Receives `QuoteRequest`
- Sends `QuoteResponse`
- Receives `PurchaseOrder`
- Sends `Invoice`
- Receives `PaymentSent`
- Sends `Receipt`
