# Architecture

## Project structure

The generated project includes the MCP server application, supporting development tools, tests, and documentation.

```text
├── mcp_server/
│   ├── app/
│   │   ├── core/
│   │   │   ├── server_lifecycle.py
│   │   │   ├── user_config.py
│   │   │   └── user_credentials.py
│   │   ├── prompts/
│   │   ├── resources/
│   │   ├── tests/
│   │   │   ├── integration/
│   │   │   └── unit/
│   │   ├── tools/
│   │   │   └── user_tools.py
│   │   └── main.py
│   ├── dev_tools/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── docs/
│   ├── tests/
│   ├── .env.template
│   ├── pyproject.toml
│   ├── pytest.ini
│   ├── Taskfile.yaml
│   ├── test_interactive.py
│   └── uv.lock
```

## Application layout

The application is organized by responsibility:

- `app/core/` contains configuration, credentials, and lifecycle hooks.
- `app/tools/` contains MCP tools, including the sample user tool.
- `app/prompts/` and `app/resources/` are loaded automatically for custom prompts and resources.
- `app/tests/` contains integration and unit tests for the application code.
- `dev_tools/` contains auxiliary developer utilities.
- `Dockerfile` and `.dockerignore` define container builds. The app root is the Docker context for custom execution-environment builds; `.dockerignore` keeps EE images deps-only while workload-docker bundles `app/` via the Files catalog.

This structure keeps runtime code, documentation, and support tooling separate while still making them easy to navigate.

## Deployment modes

`task deploy` supports two ways to host the MCP server on DataRobot, selected by `ENABLE_MCP_ON_WORKLOAD_API`:

- **Serverless (default)**&mdash;Deploys as a DataRobot Custom Model and Deployment. Used when `ENABLE_MCP_ON_WORKLOAD_API` is `false` or unset.
- **Workload (Preview)**&mdash;Deploys as a DataRobot Workload API artifact and workload, built from the Files catalog. Used when `ENABLE_MCP_ON_WORKLOAD_API` is `true`.

Run `task workload-deployment-flag-check` (invoked automatically by `task install` and `task deploy`) to confirm which mode a given `.env` resolves to before deploying.

## Configuration reference

### Required environment variables

| Variable | Description | Default |
|---|---|---|
| `DATAROBOT_API_TOKEN` | DataRobot API token | None |
| `DATAROBOT_ENDPOINT` | DataRobot instance URL | `https://app.datarobot.com` |

### MCP server settings

| Variable | Description | Default |
|---|---|---|
| `MCP_SERVER_NAME` | Server display name | `datarobot-mcp-server` |
| `MCP_SERVER_PORT` | Server port | `8080` |
| `MCP_SERVER_HOST` | Server bind address | `0.0.0.0` |
| `MCP_SERVER_LOG_LEVEL` | MCP server log level | `WARNING` |
| `APP_LOG_LEVEL` | Application log level | `INFO` |

### Deployment settings

| Variable | Description | Default |
|---|---|---|
| `ENABLE_MCP_ON_WORKLOAD_API` | Opt in to Workload API deployment instead of serverless | `false` |
| `DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT` | Reuse an existing execution environment instead of building one. Applies to serverless deployments and to Workload deployments using a generated Dockerfile; has no effect on the default Workload path, which uses a provided Dockerfile | None&mdash;builds a new execution environment |
| `DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID` | Version of the reused execution environment; only applies when `DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT` is set | None |
| `DATAROBOT_MCP_EXECUTION_ENVIRONMENT_NAME` | Name for a newly built execution environment; only applies when `DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT` is empty | `[{pulumi stack}] [{app name}]` |
| `MCP_WORKLOAD_DOCKERFILE_PATH` | Catalog-relative Dockerfile path for a Workload provided-Dockerfile build; set to `none` to use a generated Dockerfile instead | `Dockerfile` |
| `MCP_WORKLOAD_CONTAINER_PORT` | Workload container port | `8080` |
| `MCP_WORKLOAD_REPLICA_COUNT` | Workload replica count | `1` |
| `MCP_WORKLOAD_CPU` | Workload CPU allocation | `1` |
| `MCP_WORKLOAD_MEMORY` | Workload container memory, in bytes | `536870912` (512 MiB) |
| `MCP_WORKLOAD_ENCLAVE_SELECTION_POLICY` | Forces Compute Enclave placement, skipping the `ENABLE_COMPUTE_ENCLAVE` entitlement lookup that normally decides it. The workload is linked to a use case on every cluster regardless. `availability` is the only accepted value — `manual` needs an Enclave named via `runtime.enclaves` | unset: decided from the entitlement |

### Dynamic tool registration settings

| Variable | Description | Default |
|---|---|---|
| `MCP_SERVER_REGISTER_DYNAMIC_TOOLS_ON_STARTUP` | Register discovered deployments as tools during startup | `false` |
| `MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA` | Allow tool registrations with empty schemas | `false` |
| `MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR` | How to handle duplicate tool names | `warn` |

### Dynamic prompt registration settings

| Variable | Description | Default |
|---|---|---|
| `MCP_SERVER_REGISTER_DYNAMIC_PROMPTS_ON_STARTUP` | Register discovered prompts during startup | `false` |
| `MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR` | How to handle duplicate prompt names | `warn` |

### OpenTelemetry settings

| Variable | Description | Default |
|---|---|---|
| `OTEL_ENABLED` | Enable OpenTelemetry tracing | `true` |
| `OTEL_COLLECTOR_BASE_URL` | OpenTelemetry collector endpoint | Uses the DataRobot endpoint |
| `OTEL_ENTITY_ID` | Entity ID attached to traces | None |
| `OTEL_ENABLED_HTTP_INSTRUMENTORS` | Enable HTTP instrumentation | `false` |
| `OTEL_ATTRIBUTES` | Custom trace attributes as JSON | `{}` |

### AWS settings

| Variable | Description | Default |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | AWS access key | None |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | None |
| `AWS_SESSION_TOKEN` | AWS session token | None |
| `AWS_PREDICTIONS_S3_BUCKET` | S3 bucket for predictions | None |
| `AWS_PREDICTIONS_S3_PREFIX` | S3 prefix for predictions | None |

### OAuth and resource server settings

| Variable | Description | Default |
|---|---|---|
| `MCP_ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE` | Serve `/.well-known/oauth-protected-resource` without authentication | `false` |
| `MCP_OAUTH_RESOURCE` | Resource identifier published in protected-resource metadata | Resolved from the container's runtime URL |
| `MCP_OAUTH_AUTHORIZATION_SERVERS` | Authorization server URL(s), comma-separated | None |
| `MCP_OAUTH_SCOPE_SOURCE` | Which scope declaration mechanism is enforced: `both`, `code`, or `tags` | `both` |
| `MCP_OAUTH_TAG_SCOPES_<TAG>` | Required scopes for tools with the tag `<TAG>`, comma-separated | None |

### Cross-Application Access settings

| Variable | Description | Default |
|---|---|---|
| `MCP_XAA_TRUSTED_ISSUER` | Trusted issuer URL used in the XAA token exchange step | None |
| `MCP_XAA_EXCHANGE_AUDIENCE` | Authorization server URL with the audience ID for token exchange | None |
| `MCP_XAA_TOKEN_URL` | Authorization server token request URL | None |
| `MCP_XAA_SCOPES` | Scope to be authorized by the authorization server | None |
| `MCP_XAA_TOKEN_AUDIENCE` | Expected audience on XAA tokens, validated by this server. Leaving it unset skips audience validation | None |
| `MCP_XAA_TOKEN_ENDPOINT_AUTH_METHOD` | Token endpoint authentication method (`private_key_jwt` is the only method implemented today) | None |
| `MCP_ENABLE_OAUTH_CLAIM_VALIDATION` | Validate the XAA token in `x-datarobot-external-access-token` on each request | `false` |

The four `MCP_XAA_*` variables above `MCP_XAA_TOKEN_AUDIENCE` are all-or-nothing: set every one of them, or the deployment fails. For a full walkthrough of these settings, see [OAuth resource-server authentication](oauth_authentication.md).

## Custom configuration

Add application-specific settings in `mcp_server/app/core/user_config.py`. The generated project already defines `UserAppConfig`, so extend that class instead of replacing it.

Example:

```python
from datarobot.core.config import DataRobotAppFrameworkBaseSettings


class UserAppConfig(DataRobotAppFrameworkBaseSettings):
    user_name: str = "default-user"
    custom_api_endpoint: str = "https://api.example.com"
```

`DataRobotAppFrameworkBaseSettings` automatically loads values from (in priority order): environment variables (including `MLOPS_RUNTIME_PARAM_*`), `.env` file, file secrets, and `pulumi_config.json`. Fields are matched by name — `user_name` reads from `USER_NAME` env var.
