# Green Valley

Green Valley is the self-onboarded farm that proves AgriBroker can grow beyond the original seeded sellers.

## Catalog

- Item: tomatoes
- Stock: 300
- Unit price: $0.42
- Stripe account: `acct_demo_green_valley`

## Role

Green Valley was added through:

```bash
python scripts/onboard_farmer.py --name "Green Valley" --item tomatoes --stock 300 --price 0.42 --floor 0.38 --no-stripe
```

The onboarding flow generated a simulated Stripe connected account, appended the farm to `config/farms.json`, and made it eligible for optimization.

## Demo Behavior

Before Green Valley, the standard 500 tomato order cost $215. After onboarding Green Valley, the optimizer chooses:

- Farm A: 200 tomatoes at $0.40 = $80
- Green Valley: 300 tomatoes at $0.42 = $126
- Total: $206

That makes Green Valley the clearest proof that onboarding changes real marketplace outcomes.

## Protocol Messages

- Receives `QuoteRequest`
- Sends `QuoteResponse`
- Receives `PurchaseOrder`
- Sends `Invoice`
- Receives `PaymentSent`
- Sends `Receipt`
