# AgriBroker Registry

The AgriBroker Registry is the seller discovery agent for the produce marketplace.

It receives catalog registrations from farm agents, indexes sellers by item, and returns the active seller addresses that can quote a buyer request.

## Role

- Accepts `RegisterCatalog` messages from farms.
- Stores which agents sell tomatoes and other produce.
- Responds to `WhoSells` with a deterministic `SellerList`.
- Lets the orchestrator discover sellers without hardcoding farm addresses.

## Demo Behavior

For the current tomatoes demo, the registry should discover:

- Farm A
- Farm B
- Farm C
- Sunny Acres
- Green Valley

The buyer-facing AgriBroker agent uses this registry in live agent discovery mode.

## Protocol Messages

- `RegisterCatalog`: farm address plus catalog items.
- `WhoSells`: item lookup request.
- `SellerList`: sorted seller addresses for that item.

## Positioning

This agent is deliberately simple and transparent. It proves that AgriBroker is a multi-agent marketplace, not a single chatbot with hardcoded suppliers.
