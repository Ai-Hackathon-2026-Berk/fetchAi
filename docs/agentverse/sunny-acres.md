# Sunny Acres — Flockx Business Agent

Sunny Acres is AgriBroker's **verified-brand seller**. It is built as a real
**Fetch.ai Business Agent** (no-code, via Flockx) to prove AgriBroker can transact with
the production Business product — and it is mirrored by a code-backed farm agent so the
live procurement/optimization demo stays reliable.

| | |
|---|---|
| Item | tomatoes |
| Stock | 300 |
| Unit price | $0.48 each |
| Stripe account | `acct_demo_sunny_acres` |

## Why a hybrid (Business Agent + code fallback)

Flockx Business Agents are **conversational, A2A-capable, and auto-indexed by ASI:One and
Agentverse** — perfect as a discoverable verified storefront. For the *live* run we still
quote Sunny Acres through the code farm agent so the optimizer always has a fast,
structured, parseable quote even if the hosted Business Agent is slow or offline. The
result: real Business-product usage **and** a demo that never breaks.

- **Showcase:** discover + chat with the real Sunny Acres Business Agent through ASI:One
  (captured in the demo video).
- **Live pipeline:** the code Sunny Acres farm participates in quote discovery and can win
  orders when cheaper farms run short on stock.

## Build it on Flockx (no-code, ~5 minutes)

You need a Flockx/Fetch login. Reference docs:
<https://docs.flockx.io/documentation/getting-started/create-agent>

1. Go to **business.fetch.ai** (the Flockx Workbench) and sign in.
2. **Create a new Business Agent.** Name it `Sunny Acres`; pick a produce/grocery category.
3. **Identity & tone:** a friendly, verified-brand tomato grower that gives quick, clear
   price quotes for bulk orders.
4. **Knowledge** — paste the catalog so it quotes consistently with the demo:

   ```
   Sunny Acres sells vine-ripened tomatoes.
   Availability: 300 units in stock.
   Price: $0.48 per tomato (per unit), for any quantity up to 300.
   For an order of N tomatoes (N <= 300), the quote is N * $0.48.
   Always answer a quote request in this exact format:
   "Sunny Acres can supply <N> tomatoes at $0.48 each (total $<N*0.48>)."
   ```

   The fixed answer format is what AgriBroker's `parse_natural_language_quote()` reads, so
   keep the `<N> ... $0.48 each` phrasing.
5. **Enable the Chat Protocol / ASI:One discoverability** option so the agent is reachable
   in chat and indexed by ASI:One.
6. **Deploy.** Flockx publishes it to Agentverse automatically.
7. **Capture for the submission:**
   - the agent **address** (`agent1q…`),
   - its **Agentverse profile URL**,
   - its **ASI:One** discoverable handle/name.

   Record these in `docs/agentverse-profile.md` and the Devpost deliverables list.

## Showcase it via ASI:One (for the video)

1. In ASI:One, search for / open **Sunny Acres**.
2. Ask: `How much for 300 tomatoes?`
3. Confirm it replies with the quote in the expected format.
4. Then run the full AgriBroker buyer flow (`I need 500 tomatoes under $250.`) and narrate
   that Sunny Acres is the verified Business Agent storefront, quoted live in the optimizer
   through its code-backed counterpart for reliability.

## Live quote integration (implemented)

AgriBroker can fetch Sunny Acres' price **live, agent-to-agent over the Chat Protocol**,
and feed it into the optimizer. Enable it by setting the Business Agent's address:

```env
AGRIBROKER_BUSINESS_SELLER_ADDRESS=agent1q...   # from the Flockx Agent Network / profile
AGRIBROKER_BUSINESS_SELLER_NAME=Sunny Acres
```

How it works (`agents/business_seller.py` + `agents/asi_chat_agent.py`):

1. On each buyer request, AgriBroker sends Sunny Acres a natural-language message
   ("How much for N tomatoes?") and waits up to `BUSINESS_QUOTE_TIMEOUT` seconds.
2. The reply is parsed with `parse_natural_language_quote()` into a structured `Quote`.
3. That quote **overlays the Sunny Acres farm** in the optimizer, so it can genuinely win
   part of the order — and settlement reuses the existing Sunny Acres account.
4. The quantity is clamped to real stock, and any timeout / unparseable reply **falls back**
   to the seeded catalog price. The live demo never blocks or breaks.

Leave `AGRIBROKER_BUSINESS_SELLER_ADDRESS` blank to run purely on the seeded price.

## Code fallback (always present)

The code Sunny Acres farm lives in `config/farms.json` and speaks the structured protocol
used by the optimizer, and is what the live overlay falls back to:

- Receives `QuoteRequest` → sends `QuoteResponse`
- Receives `PurchaseOrder` → sends `Invoice`
- Receives `PaymentSent` → sends `Receipt`
```
