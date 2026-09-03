# Agent-to-Agent (A2A)

Template agents can expose themselves as A2A servers and connect to remote agents via the agent-to-agent protocol. For authentication configuration, see [A2A authentication](./agent2agent-auth.md).

To expose an agent via A2A:

- Ensure the template has a `general.front_end.a2a` configuration block. Templates include this by default.

To connect an agent to a remote agent via A2A:

- Uncomment the `function_groups` and `workflow.tool_names` blocks in `workflow.yaml`.
- Run `task deploy-dev` (or `dr start`) so Pulumi provisions a MemorySpace for the agent card registry L2 cache and injects `AGENT_CARD_REGISTRY_MEMORY_SPACE_ID`. See [Central registry (`registry`)](#central-registry-registry).

Enable the `ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS` feature flag in DataRobot to use environment variables in `workflow.yaml` files.

### Agent cards and DataRobot deployments

When the `ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT` feature flag is enabled, deploying an agent that exposes A2A server endpoints stores the agent card in DataRobot. Use the following endpoints:

- List deployments with agent cards—`GET deployments/?isA2AAgent=true`.
- Retrieve an agent card—`GET deployments/DEPLOYMENT_ID/agentCard`.

## Unauthenticated agent card access

Anonymous `GET /.well-known/agent-card.json` requests are opt-in. By default, unauthenticated requests receive `401 Unauthorized`.

| Caller | Result |
|--------|--------|
| Authenticated (gateway identity headers present) | Full agent card |
| Unauthenticated, `enable_unauthenticated_well_known_route: false` (default) | `401 Unauthorized` |
| Unauthenticated, `enable_unauthenticated_well_known_route: true` | Redacted agent card (skills and identity extensions stripped) |

Platform administrators must also enable unauthenticated routing per cluster before the well-known route is reachable for anonymous callers on deployed agents.

On the **Workload API** runtime (`ENABLE_AGENT_ON_WORKLOAD_API=true`), setting this flag also adds an optional-auth route for `/a2a/.well-known/agent-card.json` to the workload artifact specification during deploy. See [Deployment runtimes](./deployment-runtimes.md#anonymous-agent-card-discovery).

```yaml
general:
  front_end:
    a2a:
      enable_unauthenticated_well_known_route: true
      server:
        name: "My Agent"
        description: "An example agent."
```

## Agent card resolution

Before the first RPC call, the client fetches the remote agent card — a JSON document describing the agent capabilities and authentication requirements. There are two mutually exclusive ways to obtain it.

### Direct fetch (`url`)

Use this when the remote agent card endpoint is directly reachable with the same credentials used for RPC calls — typically when calling a DataRobot-hosted agent with DataRobot API key auth. The client fetches the card from `{url}/.well-known/agent-card.json`, then uses the same `auth_provider` for all subsequent RPC calls. This is the setup used in the default template.

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: datarobot_auth
```

This approach is the simplest, but it assumes the card is accessible before authentication is fully resolved. It is not suitable when the card endpoint requires a different auth flow than the RPC calls — for example, with Okta XAA, where the card itself describes how to authenticate (a circular dependency). In that case, use the central registry instead.

When testing locally and the URL points at the dev server (for example, `http://localhost:8842/a2a/`), unauthenticated requests to the card endpoint return `401` by default. Send gateway identity headers for the full card, or enable `enable_unauthenticated_well_known_route` for a redacted card. See [Debugging agents → Local agent card](./debugging.md#local-agent-card) and [Unauthenticated agent card access](#unauthenticated-agent-card-access).

### Central registry (`registry`)

Use this when calling a DataRobot-hosted agent protected by Okta XAA or any other flow where the card endpoint requires auth that is not yet available before the card is read. The central agent card registry exposes all agent cards in the tenant at a single endpoint that requires only a standard `DATAROBOT_API_TOKEN`, bypassing the per-agent auth requirement for card discovery.

The RPC base URL is derived from the `url` advertised on the card; specifying it separately is not necessary. When a workflow has many registry-backed function groups, all cards are resolved in a maximum of two HTTP calls (one for deployment IDs, one for external IDs) and cached in-memory until the TTL expires.

Registry lookups use a two-tier cache:

| Tier | Backend | Scope |
|------|---------|-------|
| L1 | In-process memory | Single worker / replica |
| L2 | DataRobot MemorySpace (`AGENT_CARD_REGISTRY_MEMORY_SPACE_ID`) | Shared across replicas and pod restarts |

When `AGENT_CARD_REGISTRY_MEMORY_SPACE_ID` is set, resolved agent cards are written through to the MemorySpace-backed L2 cache so every replica shares the same registry snapshot. If a registry refresh fails, a card may still be served from cache while it remains within `AGENT_CARD_REGISTRY_CACHE_TTL` (stale-if-error).

> [!IMPORTANT]
> When you connect to remote agents via A2A (`authenticated_a2a_client` in `function_groups`), Pulumi provisions a dedicated MemorySpace for the registry L2 cache and injects `AGENT_CARD_REGISTRY_MEMORY_SPACE_ID` as a runtime parameter. Run `task deploy-dev` (or `dr start`) after uncommenting remote A2A client blocks so the space is created and the ID is written to `.env`. This cache is separate from [agent memory](./agent-memory.md) (`AGENT_MEMORY_SPACE_ID`).

Lookup by deployment ID — use when the DataRobot deployment ID of the remote agent is known:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    registry:
      deployment_id: "64a1b2c3d4e5f6a7b8c9d0e1"
    auth_provider: okta_auth
```

Lookup by external ID — use when the remote agent publishes a stable catalog identifier via `general.front_end.a2a.external.id` in its `workflow.yaml`. This decouples the configuration from deployment IDs, which can change across environments:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    registry:
      external_id: "my-remote-agent"
    auth_provider: okta_auth
```

> **Warning:** `external.id` is not validated or enforced for uniqueness by DataRobot — multiple agents can be registered under the same external ID. Use `AGENT_CARD_REGISTRY_ON_DUPLICATE` to control how the registry resolves such conflicts.

#### Registry environment variables

The registry lookup honors the following environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATAROBOT_API_TOKEN` | Yes | DataRobot API token for registry authentication. |
| `DATAROBOT_ENDPOINT` | Yes | DataRobot API base URL, for example, `https://app.datarobot.com/api/v2`. |
| `AGENT_CARD_REGISTRY_CACHE_TTL` | No | Cache TTL in seconds. Default `86400` (24 hours). Set to `0` to disable caching. |
| `AGENT_CARD_REGISTRY_TIMEOUT` | No | HTTP timeout in seconds for registry requests. Default `30`. |
| `AGENT_CARD_REGISTRY_ON_DUPLICATE` | No | Resolution strategy when multiple cards share the same external ID: `first` (default) keeps the earliest registered card, `last` keeps the most recently registered card, `error` raises an exception. `first` is recommended for stability — `last` and `error` may alter agent behavior if a duplicate is introduced later. |
| `AGENT_CARD_REGISTRY_MEMORY_SPACE_ID` | No | DataRobot MemorySpace ID for the registry L2 cache. Provisioned automatically when remote A2A clients are configured in `workflow.yaml`; shared across replicas. When unset, only in-process L1 caching is used. |


## Configuration reference

The following sections list the configuration fields for A2A function groups.

### `authenticated_a2a_client` function group

The `authenticated_a2a_client` function group supports the following fields:

| Field | Default | Description |
|-------|---------|-------------|
| `url` | — | Base URL for direct card fetch. Mutually exclusive with `registry`. |
| `registry` | — | Registry lookup block. Mutually exclusive with `url`. |
| `auth_provider` | `None` | Name of an `authentication` entry for A2A RPC calls. |
| `agent_card_path` | `/.well-known/agent-card.json` | Card path for direct fetch — ignored when using `registry`. |

### `registry` block

Exactly one field must be set.

| Field | Description |
|-------|-------------|
| `deployment_id` | DataRobot deployment ID. |
| `external_id` | External agent catalog identifier. |

## Agent card identity: `external`

Optional fields under `general.front_end.a2a.external` publish additional identity metadata on the agent card and allow overriding the auto-generated agent card URL.

| Field | Purpose |
|-------|---------|
| `external.id` | Catalog discovery identifier. Emitted as the `urn:datarobot:agent:identity:external` extension on the agent card. |
| `external.url` | Overrides the auto-generated agent card endpoint URL. |

```yaml
general:
  front_end:
    a2a:
      external:
        id: "my-agent-id"
        url: "https://my-agent-id.example.com/a2a/"
```

> **Warning:** `external.id` and `external.url` are not validated by DataRobot. Incorrect values may result in a wrong entry-point URL or duplicate registrations — for example, if two agents are deployed with the same identifier. Use `AGENT_CARD_REGISTRY_ON_DUPLICATE` to control resolution behavior. See [Registry environment variables](#registry-environment-variables) for details.


## A2A agents hosted outside of DataRobot

For A2A agents hosted outside of DataRobot:

1. Create an external model with the **Agentic Workflow** target type and the default configuration.
2. Deploy the external model.
3. Push the agent card via `PUT deployments/DEPLOYMENT_ID/agentCard`.

For external deployments, remove the agent card with `DELETE deployments/DEPLOYMENT_ID/agentCard`.

```python
deployments = dr.Deployment.list(filters=DeploymentListFilters(is_a2a_agent=True))
agent_card = deployment.get_agent_card()
# Only available for external deployments.
deployment.upload_agent_card(agent_card)
deployment.delete_agent_card()
```
