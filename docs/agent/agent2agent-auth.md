# A2A authentication

This page outlines how to configure authentication for Agent-to-Agent (A2A) communication. There are two supported authentication methods:

1. DataRobot API key — A simple bearer token auth for DataRobot-hosted agents. Configured by default in all templates.
2. Okta cross-application access (XAA) — A two-step token exchange for federated Okta environments (hybrid RFC 8693 / RFC 7523 flow). Opt-in via `workflow.yaml`.

Both methods use the `authenticated_a2a_client` function group on the client side. See [Agent-to-Agent (A2A)](./agent2agent.md) for how to expose A2A endpoints and connect to remote agents.

## Option 1: DataRobot API key authentication

This is the default and requires no additional configuration. The `datarobot_auth` provider is already defined in all generated `workflow.yaml` files.

### How it works

On each A2A call, the `datarobot_api_key` auth provider injects `DATAROBOT_API_TOKEN` as an `Authorization: Bearer <token>` header. The A2A endpoint of the remote agent validates the token against the DataRobot platform.

### `workflow.yaml` configuration for DataRobot API key authentication

The template already includes this configuration:

```yaml
authentication:
  datarobot_auth:
    _type: datarobot_api_key
```

To connect to a remote agent using DataRobot API key auth, uncomment the `remote_agent` block in `workflow.yaml`:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: datarobot_auth
```

## Option 2: Okta cross-application access (XAA)

Use this when calling an agent protected by Okta's federated identity model. The flow obtains a scoped access token through a two-step exchange.

### Prerequisites

- An Okta organization with Cross-Application Access enabled.
- A registered AI agent principal in Okta with a private key pair.
- `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` environment variables in the `.env` file (default), or the same values supplied via `principal_id` / `private_jwk` in `workflow.yaml` as described under [Environment variables](#environment-variables).

### Environment variables

| Variable | Description |
|----------|-------------|
| `IDP_AGENT_ID` | Okta AI agent principal ID used in the XAA token exchange flow (as `iss`/`sub` in JWT client assertions). Also used by the API gateway to enforce audience matching when an external IDP is configured. |
| `IDP_AGENT_PRIVATE_KEY_JWK` | Base64-encoded or raw-JSON private JWK. Required for the XAA token exchange flow — the agent uses it to sign JWT client assertions for authentication and grant generation. |

Both load automatically from environment variables, `.env`, or DataRobot runtime parameters when `principal_id` or `private_jwk` are not set on the `okta_cross_app_access` block.

Alternatively, define `principal_id` and `private_jwk` directly under `authentication.okta_auth` (or whichever key holds `_type: okta_cross_app_access`) in `workflow.yaml`:

- Static values — Use a plain string for the Okta principal ID or for the private JWK (same formats as the `IDP_AGENT_ID` / `IDP_AGENT_PRIVATE_KEY_JWK` environment variables).
- Dynamic values — Use placeholders of the form `${VAR_NAME}` so the value is read from an environment variable at runtime when the workflow is loaded. This requires the `ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS` feature flag to be enabled in DataRobot so `${VAR_NAME}` entries in `workflow.yaml` are substituted from the environment.

### Installation

The `auth` extra is included in the generated `pyproject.toml` and provides the `okta-client-python` dependency. No additional installation steps are required.

### `workflow.yaml` configuration for Okta XAA

1. Enable XAA on the A2A server for this agent (server-side). Uncomment the `cross_application_access` block under `general.front_end.a2a`:

```yaml
general:
  front_end:
    _type: dragent_fastapi
    a2a:
      server:
        name: "My Agent"
        description: "My agent description."
      cross_application_access:
        token_exchange:
          trusted_issuer: "https://your-org.okta.com"
          audience: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX"
        token_request:
          token_url: "https://your-org.okta.com/oauth2/ausXXXXXXXXXXXXXXX/v1/token"
          audience: "https://example.com/agents/my-agent-id"
          scopes:
            - "dr.impersonation"
```

2. Add the Okta auth provider (client-side). Uncomment the `okta_auth` block in the `authentication` section:

```yaml
authentication:
  datarobot_auth:
    _type: datarobot_api_key
  okta_auth:
    _type: okta_cross_app_access
```

3. Connect to a remote XAA-protected agent. Uncomment and configure the `remote_agent` function group:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/<deployment-id>/directAccess/a2a/"
    auth_provider: okta_auth
```

### Infrastructure: automatic runtime parameter provisioning

For the general runtime parameter mechanism, see [Runtime parameters](./runtime-parameters.md).

The infra module provisions `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` as runtime parameters automatically whenever the corresponding environment variables are set at `dr run deploy` time:

- `IDP_AGENT_ID` — Injected as a plain string runtime parameter from the `IDP_AGENT_ID` environment variable.
- `IDP_AGENT_PRIVATE_KEY_JWK` — Stored securely as a DataRobot credential (`ApiTokenCredential`) and injected as a `credential`-type runtime parameter from the `IDP_AGENT_PRIVATE_KEY_JWK` environment variable.

Set both in the `.env` file before running `dr run deploy`.

### How XAA works

The XAA flow operates in two steps:

1. Token Exchange (RFC 8693) — The incoming Okta access token from the caller is exchanged for an ID-JAG (Identity Assertion Authorization Grant) via the org-level Authorization Server (`token_exchange.trusted_issuer`).
2. JWT Bearer Grant (RFC 7523) — The ID-JAG is exchanged for a scoped access token at the resource AS token endpoint (`token_request.token_url`), granting access to the target agent with the requested scopes.

Both steps authenticate the client using a private JWT key, signing assertions with the key from `IDP_AGENT_PRIVATE_KEY_JWK`.

## Server-side configuration reference: `cross_application_access`

| Field | Required | Purpose |
|-------|----------|---------|
| `token_exchange.trusted_issuer` | Yes | Org-level Authorization Server issuer URL. |
| `token_exchange.audience` | Yes | Resource AS base URL (where ID-JAG is fetched from). |
| `token_request.token_url` | Yes | Token endpoint of the resource AS. |
| `token_request.audience` | Yes | Final resource identifier for the agent. |
| `token_request.scopes` | No | Scopes the caller must request. Defaults to `["read_data"]`. |

## Client-side configuration reference: `okta_cross_app_access`

| Field | Default | Purpose |
|-------|---------|---------|
| `okta_token_header` | `x-datarobot-external-access-token` | Incoming request header carrying the Okta access token from the caller. |
| `principal_id` | `IDP_AGENT_ID` environment variable | Okta AI agent principal ID used in JWT client assertions for the XAA exchange. |
| `private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` environment variable | Private JWK used to sign JWT client assertions for the XAA exchange. |

Example with non-default options:

```yaml
authentication:
  okta_auth:
    _type: okta_cross_app_access
    okta_token_header: "x-custom-header"
    # principal_id: "my-agent-principal-id"  # Optional: override IDP_AGENT_ID environment variable
    # private_jwk: "..."                     # Optional: override IDP_AGENT_PRIVATE_KEY_JWK environment variable
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Header 'x-datarobot-external-access-token' not found` | The incoming request doesn't carry the Okta token. | Ensure the upstream caller forwards the Okta access token in the expected header. |
| `ValueError: principal_id is required` | `IDP_AGENT_ID` environment variable not set. | Set `IDP_AGENT_ID` in the `.env` file or runtime parameters. |
| `ValueError: Could not parse private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` is neither valid base64-encoded JSON nor raw JSON. | Verify the JWK — try `echo $IDP_AGENT_PRIVATE_KEY_JWK | base64 -d | python -m json.tool`. |
| `ValueError: Agent card ... missing required fields` | Remote agent card doesn't have the XAA extension. | Verify the remote agent has `cross_application_access` configured in its `workflow.yaml`. |
| `RuntimeError: Failed to fetch agent card` | Network/auth issue reaching the agent card URL. | Check the `url` in the `function_groups` config and network connectivity. |
| `GET /.well-known/agent-card.json` returns 401 when testing locally | Unauthenticated access is disabled by default (`datarobot-genai` 0.27.0+). | Send `X-DataRobot-User-Id` (any value) or `X-DataRobot-Authorization-Context` for the full card, or set `enable_unauthenticated_well_known_route: true` in `workflow.yaml` to allow a redacted card. See [Debugging agents → Local agent card](./debugging.md#local-agent-card). |
| Agent card shows `"skills": []` when testing locally | Unauthenticated request with `enable_unauthenticated_well_known_route: true` returns a redacted card. | Send `X-DataRobot-User-Id` (any value) or `X-DataRobot-Authorization-Context` on the request for the full card. See [Debugging agents → Local agent card](./debugging.md#local-agent-card). |
| `IDP_AGENT_PRIVATE_KEY_JWK` not provisioned to runtime | The variable was not set in `.env` at deploy time. | Set `IDP_AGENT_PRIVATE_KEY_JWK` in the `.env` file and redeploy. |
