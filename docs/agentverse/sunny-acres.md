# Sunny Acres

Sunny Acres is the verified-brand seller in the AgriBroker demo.

## Catalog

- Item: tomatoes
- Stock: 300
- Unit price: $0.48
- Stripe account: `acct_demo_sunny_acres`

## Role

Sunny Acres is represented in code as a normal farm agent so the procurement demo stays reliable. It is also the intended candidate for a Fetch Business Agent storefront.

## Demo Behavior

Sunny Acres participates in quote discovery and can win orders when cheaper farms do not have enough supply. In the final presentation, Sunny Acres can be shown as the bridge between code-backed uAgents and a Business Agent storefront.

## Business Agent Plan

Create a Sunny Acres Business Agent with:

- Friendly verified-brand tone.
- Tomato catalog: 300 available at $0.48 each.
- Clear answer format for quotes.
- Fallback to this code agent for live optimization reliability.

## Protocol Messages

- Receives `QuoteRequest`
- Sends `QuoteResponse`
- Receives `PurchaseOrder`
- Sends `Invoice`
- Receives `PaymentSent`
- Sends `Receipt`
