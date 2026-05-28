# Agent-to-Agent (A2A)

Template agents can expose themselves as A2A servers and connect to remote agents via the agent-to-agent protocol. For authentication configuration, see [A2A Authentication](./agent2agent-auth.md).

To expose an agent via A2A:

- Ensure the template has a `general.front_end.a2a` configuration block. Templates include this by default.
- Run the agent with the experimental DRAgent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

To connect an agent to a remote agent via A2A:

- Uncomment the `function_groups` and `workflow.tool_names` blocks in `workflow.yaml`.
- Run the agent with the experimental DRAgent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

Enable the **ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS** feature flag in DataRobot to use environment variables in `workflow.yaml` files.

### Agent cards and DataRobot deployments

When the `ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT` feature flag is enabled and you deploy an agent that exposes A2A server endpoints, the agent card is stored in DataRobot during deployment. Use the following endpoints:

- **List deployments with agent cards**&mdash;`GET deployments/?isA2AAgent=true`.
- **Retrieve an agent card**&mdash;`GET deployments/DEPLOYMENT_ID/agentCard`.

## Agent card resolution

Before the first RPC call, the client fetches the remote agent's **agent card** — a JSON document describing the agent's capabilities and authentication requirements. There are two mutually exclusive ways to obtain it.

### Direct fetch (`url`)

Use this when the remote agent's card endpoint is directly reachable with the same credentials used for RPC calls — typically when calling a DataRobot-hosted agent with DataRobot API key auth. The client fetches the card from `{url}/.well-known/agent-card.json`, then uses the same `auth_provider` for all subsequent RPC calls. This is the setup used in the default template.

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: datarobot_auth
```

This approach is the simplest, but it assumes the card is accessible before authentication is fully resolved. It is not suitable when the card endpoint requires a different auth flow than the RPC calls — for example, with Okta XAA, where the card itself describes how to authenticate (a chicken-and-egg problem). In that case, use the central registry instead.

### Central registry (`registry`)

Use this when calling a DataRobot-hosted agent protected by Okta XAA or any other flow where the card endpoint requires auth that is not yet available before the card is read. The **central agent card registry** exposes all agent cards in the tenant at a single endpoint that requires only a standard `DATAROBOT_API_TOKEN`, bypassing the per-agent auth requirement for card discovery.

The RPC base URL is derived from the card's advertised `url` — you do not need to specify it separately. When a workflow has many registry-backed function groups, all cards are resolved in a maximum of two HTTP calls (one for deployment IDs, one for external IDs) and cached in-memory until the TTL expires.

**Lookup by deployment ID** — use when you know the DataRobot deployment ID of the remote agent:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    registry:
      deployment_id: "64a1b2c3d4e5f6a7b8c9d0e1"
    auth_provider: okta_auth
```

**Lookup by external ID** — use when the remote agent publishes a stable catalogue identifier via `general.front_end.a2a.external.id` in its `workflow.yaml`. This decouples your config from deployment IDs, which can change across environments:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    registry:
      external_id: "my-remote-agent"
    auth_provider: okta_auth
```

> [!WARNING]
> `external.id` is not validated or enforced for uniqueness by DataRobot — multiple agents can be registered under the same external ID. Use `AGENT_CARD_REGISTRY_ON_DUPLICATE` to control how the registry resolves such conflicts.

#### Registry environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATAROBOT_API_TOKEN` | Yes | DataRobot API token for registry authentication. |
| `DATAROBOT_ENDPOINT` | Yes | DataRobot API base URL, e.g. `https://app.datarobot.com/api/v2`. |
| `AGENT_CARD_REGISTRY_CACHE_TTL` | No | Cache TTL in seconds. Default `86400` (24 h). Set to `0` to disable caching. |
| `AGENT_CARD_REGISTRY_TIMEOUT` | No | HTTP timeout in seconds for registry requests. Default `30`. |
| `AGENT_CARD_REGISTRY_ON_DUPLICATE` | No | Resolution strategy when multiple cards share the same external ID: `first` (default) keeps the earliest registered card, `last` keeps the most recently registered card, `error` raises an exception. `first` is recommended for stability — `last` and `error` may alter agent behaviour if a duplicate is introduced later. |

## Configuration reference

### `authenticated_a2a_client` function group

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
| `external_id` | External agent catalogue identifier. |

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

> [!WARNING]
> `external.id` and `external.url` are not validated by DataRobot. Incorrect values may result in a wrong entry-point URL or duplicate registrations — for example, if two agents are deployed with the same identifier. Use `AGENT_CARD_REGISTRY_ON_DUPLICATE` to control resolution behaviour. See [Registry environment variables](#registry-environment-variables) for details.


## A2A agents hosted outside of DataRobot

For A2A agents hosted outside of DataRobot:

1. Create an external model with the "Agentic Workflow" target type and the default configuration.
2. Deploy the external model.
3. Push the agent card via `PUT deployments/DEPLOYMENT_ID/agentCard`.

For external deployments, you can also remove the agent card with `DELETE deployments/DEPLOYMENT_ID/agentCard`.

```python
deployments = dr.Deployment.list(filters=DeploymentListFilters(is_a2a_agent=True))
agent_card = deployment.get_agent_card()
# Only available for external deployments.
deployment.upload_agent_card(agent_card)
deployment.delete_agent_card()
```
