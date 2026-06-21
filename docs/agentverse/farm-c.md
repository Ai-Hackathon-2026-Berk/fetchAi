# Farm C

Farm C is the premium backup supplier in the AgriBroker tomatoes marketplace.

## Catalog

- Item: tomatoes
- Stock: 100
- Unit price: $0.50
- Stripe account: `acct_demo_farm_c`

## Role

Farm C is useful when demand exceeds cheaper suppliers. Its higher price makes it a backup source in the optimizer, which helps demonstrate split-order reasoning and shortfall handling.

## Demo Behavior

For normal 500 tomato orders, Farm C usually does not win because lower-cost farms can satisfy the request. For larger orders, it may be selected after Farm A, Green Valley, and Farm B.

## Protocol Messages

- Receives `QuoteRequest`
- Sends `QuoteResponse`
- Receives `PurchaseOrder`
- Sends `Invoice`
- Receives `PaymentSent`
- Sends `Receipt`
