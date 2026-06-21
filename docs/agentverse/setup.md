# Agentverse Setup

Use this checklist when making the AgriBroker agents visible in Agentverse.

## Recommended Live Demo

Keep the buyer-facing demo reliable:

```env
AGRIBROKER_DISCOVERY_MODE=local
AGRIBROKER_BUYER_PAYMENT_MODE=stripe
AGRIBROKER_FARM_PAYMENT_MODE=stripe_connect
STRIPE_CONNECT_TRANSFERS_ENABLED=false
```

Run the ASI chat agent:

```bash
python -m agents.asi_chat_agent
```

Connect its mailbox from the Inspector URL, then chat through ASI:One.

## Supporting Agent Profiles

To make the supporting uAgents appear on Agentverse, run them and connect their mailboxes from each Inspector URL.

Registry:

```bash
python -m agents.registry_agent
```

Farm agents:

```bash
python -m agents.farmer_agent --name "Farm A" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Farm B" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Farm C" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Sunny Acres" --registry <REGISTRY_ADDRESS>
python -m agents.farmer_agent --name "Green Valley" --registry <REGISTRY_ADDRESS>
```

Structured orchestrator:

```bash
python -m agents.orchestrator_agent
```

## What Judges Should Use

Judges should chat with the main AgriBroker ASI agent. The Registry and Farmer agents are supporting infrastructure that demonstrate the multi-agent marketplace behind the chat experience.

## Business Agent Boundary

Sunny Acres is the best candidate for a Fetch Business Agent. For demo reliability, keep the code-backed Sunny Acres farm in the optimizer and show the Business Agent as the verified storefront representation.
