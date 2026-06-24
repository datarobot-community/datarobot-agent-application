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
│   ├── docker/
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
- `docker/` contains the container entrypoint and Docker build files.

This structure keeps runtime code, documentation, and support tooling separate while still making them easy to navigate.

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
