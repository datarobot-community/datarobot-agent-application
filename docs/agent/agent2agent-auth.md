# A2A Authentication

This page outlines how to configure authentication for Agent-to-Agent (A2A) communication. There are two supported authentication methods:

1. **DataRobot API key** — A simple bearer token auth for DataRobot-hosted agents. Configured by default in all templates.
2. **Okta cross-application access (XAA)** — A two-step token exchange for federated Okta environments (hybrid RFC 8693 / RFC 7523 flow). Opt-in via `workflow.yaml`.

Both methods use the `authenticated_a2a_client` function group on the client side. See [Agent2Agent](./agent2agent.md) for how to expose A2A endpoints and connect to remote agents.

## Option 1: DataRobot API key authentication

This is the default and requires no additional configuration. The `datarobot_auth` provider is already defined in all generated `workflow.yaml` files.

### How it works

On each A2A call, the `datarobot_api_key` auth provider injects `DATAROBOT_API_TOKEN` as an `Authorization: Bearer <token>` header. The remote agent's A2A endpoint validates the token against the DataRobot platform.

### `workflow.yaml`

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
- `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` environment variables in your `.env` file (default), or the same values supplied via `principal_id` / `private_jwk` in `workflow.yaml` as described under [Environment variables](#environment-variables).

### Environment variables

| Variable | Description |
|----------|-------------|
| `IDP_AGENT_ID` | Okta AI agent principal ID used in the XAA token exchange flow (as `iss`/`sub` in JWT client assertions). Also used by the API gateway to enforce audience matching when an external IDP is configured. |
| `IDP_AGENT_PRIVATE_KEY_JWK` | Base64-encoded or raw-JSON private JWK. Required for the XAA token exchange flow — the agent uses it to sign JWT client assertions for authentication and grant generation. |

Both are loaded automatically from env vars, `.env`, or DataRobot Runtime Parameters when you do not set `principal_id` or `private_jwk` on the `okta_cross_app_access` block.

You can instead define **`principal_id`** and **`private_jwk`** directly under `authentication.okta_auth` (or whichever key holds `_type: okta_cross_app_access`) in `workflow.yaml`:

- **Static values** — Use a plain string for the Okta principal ID or for the private JWK (same formats as the `IDP_AGENT_ID` / `IDP_AGENT_PRIVATE_KEY_JWK` environment variables).
- **Dynamic values** — Use placeholders of the form `${VAR_NAME}` so the value is read from an environment variable at **runtime** when the workflow is loaded. This requires the **ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS** feature flag to be enabled in DataRobot so `${VAR_NAME}` entries in `workflow.yaml` are substituted from the environment.

### Installation

The `auth` extra is included in the generated `pyproject.toml` and provides the `okta-client-python` dependency. No additional installation steps are required.

### `workflow.yaml` configuration

1. Enable XAA on this agent's A2A server (server-side). Uncomment the `cross_application_access` block under `general.front_end.a2a`:

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

**Step 2** — Add the Okta auth provider (client-side). Uncomment the `okta_auth` block in the `authentication` section:

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

The infra module provisions `IDP_AGENT_ID` and `IDP_AGENT_PRIVATE_KEY_JWK` as runtime parameters automatically whenever the corresponding environment variables are set at `dr run deploy` time:

- `IDP_AGENT_ID` — Injected as a plain string runtime parameter from the `IDP_AGENT_ID` environment variable.
- `IDP_AGENT_PRIVATE_KEY_JWK` — Stored securely as a DataRobot credential (`ApiTokenCredential`) and injected as a `credential`-type runtime parameter from the `IDP_AGENT_PRIVATE_KEY_JWK` environment variable.

Set both in your `.env` file before running `dr run deploy`.

### How XAA works

The XAA flow operates in two steps:

1. **Token Exchange (RFC 8693)** — The caller's incoming Okta access token is exchanged for an ID-JAG (Identity Assertion Authorization Grant) via the org-level Authorization Server (`token_exchange.trusted_issuer`).
2. **JWT Bearer Grant (RFC 7523)** — The ID-JAG is exchanged for a scoped access token at the resource AS token endpoint (`token_request.token_url`), granting access to the target agent with the requested scopes.

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
| `okta_token_header` | `x-datarobot-external-access-token` | Incoming request header carrying the caller's Okta access token. |
| `principal_id` | `IDP_AGENT_ID` env var | Okta AI agent principal ID used in JWT client assertions for the XAA exchange. |
| `private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` env var | Private JWK used to sign JWT client assertions for the XAA exchange. |

Example with non-default options:

```yaml
authentication:
  okta_auth:
    _type: okta_cross_app_access
    okta_token_header: "x-custom-header"
    # principal_id: "my-agent-principal-id"  # Optional: override IDP_AGENT_ID env var
    # private_jwk: "..."                     # Optional: override IDP_AGENT_PRIVATE_KEY_JWK env var
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Header 'x-datarobot-external-access-token' not found` | The incoming request doesn't carry the Okta token. | Ensure the upstream caller forwards the Okta access token in the expected header. |
| `ValueError: principal_id is required` | `IDP_AGENT_ID` env var not set. | Set `IDP_AGENT_ID` in your `.env` file or Runtime Parameters. |
| `ValueError: Could not parse private_jwk` | `IDP_AGENT_PRIVATE_KEY_JWK` is neither valid base64-encoded JSON nor raw JSON. | Verify your JWK — try `echo $IDP_AGENT_PRIVATE_KEY_JWK | base64 -d | python -m json.tool`. |
| `ValueError: Agent card ... missing required fields` | Remote agent card doesn't have the XAA extension. | Verify the remote agent has `cross_application_access` configured in its `workflow.yaml`. |
| `RuntimeError: Failed to fetch agent card` | Network/auth issue reaching the agent card URL. | Check the `url` in your `function_groups` config and network connectivity. |
| `IDP_AGENT_PRIVATE_KEY_JWK` not provisioned to runtime | The variable was not set in `.env` at deploy time. | Set `IDP_AGENT_PRIVATE_KEY_JWK` in your `.env` file and redeploy. |
