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

## Protocol Manifests

The agents publish named protocol manifests when they start:

| Agent | Protocol |
|---|---|
| AgriBroker ASI chat | `AgentChatProtocol` |
| Registry | `AgriBrokerRegistryProtocol` |
| Farmer agents | `AgriBrokerFarmProtocol` |
| Structured orchestrator | `AgriBrokerProcurementProtocol` |

If a protocol does not appear on Agentverse, restart the agent and confirm the terminal
shows a successful manifest/profile publish message.

## Profile Images

All code agents pass `avatar_url` and `banner_url` into the uAgent constructor. By default
these are generated public SVG image URLs so the profiles are not blank.

For final branding, replace them in `.env` with hosted HTTPS images:

```env
AGRIBROKER_AGENT_AVATAR_URL=https://your-host/agribroker-avatar.png
AGRIBROKER_AGENT_BANNER_URL=https://your-host/agribroker-banner.png
```

Optional role-specific overrides:

```env
AGRIBROKER_CHAT_AVATAR_URL=https://your-host/chat-avatar.png
AGRIBROKER_REGISTRY_AVATAR_URL=https://your-host/registry-avatar.png
AGRIBROKER_ORCHESTRATOR_AVATAR_URL=https://your-host/orchestrator-avatar.png
AGRIBROKER_FARMER_AVATAR_URL=https://your-host/farmer-avatar.png
```

Agentverse needs image URLs it can fetch publicly. Local file paths like
`assets/avatar.png` will not work unless those files are hosted somewhere public.

## What Judges Should Use

Judges should chat with the main AgriBroker ASI agent. The Registry and Farmer agents are supporting infrastructure that demonstrate the multi-agent marketplace behind the chat experience.

## Business Agent Boundary

Sunny Acres is built as a real Fetch.ai Business Agent (no-code, via Flockx) and shown as the
verified storefront, while the code-backed Sunny Acres farm stays in the optimizer for demo
reliability. See [sunny-acres.md](sunny-acres.md) for the step-by-step build + showcase guide.
