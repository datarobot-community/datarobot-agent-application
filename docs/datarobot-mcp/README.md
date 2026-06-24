# DataRobot MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that connects AI agents&mdash;Cursor, VS Code, Claude Desktop, and others&mdash;to DataRobot's predictive AI platform through a standardized tool interface.

## Overview

This component provides:

- **DataRobot tools**&mdash;Pre-built tools for interacting with DataRobot deployments, datasets, and the platform API.
- **Dynamic tool registration**&mdash;Automatically turn tagged DataRobot deployments into callable MCP tools.
- **Custom tool authoring**&mdash;Add domain-specific tools using FastMCP's decorator pattern.
- **OpenTelemetry tracing**&mdash;Built-in observability for monitoring tool calls in production.

## Use cases

- Connect an AI coding assistant (Cursor, VS Code) directly to DataRobot for predictions and data queries.
- Build autonomous agents that discover and call DataRobot deployments dynamically.
- Expose DataRobot models to any MCP-compatible client without writing a custom integration per client.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- DataRobot account and API credentials
- AWS credentials (optional, for S3 prediction features)

## Getting started

### 1. Configure environment variables

Copy `.env.template` to `.env` and set the required values:

```bash
DATAROBOT_API_TOKEN=your_api_token
DATAROBOT_ENDPOINT=https://app.datarobot.com
```

All other variables are optional. See the [configuration reference](mcp_server_architecture.md#configuration) for the full list.

### 2. Start the server locally

```bash
task dev
```

The server starts on `http://localhost:8080`. The MCP endpoint is at `http://localhost:8080/mcp/`.

### 3. Connect an MCP client

See [MCP client setup](mcp_client_setup.md) for step-by-step instructions for Cursor, VS Code, and Claude Desktop.

### 4. Deploy to DataRobot

```bash
task deploy
```

## MCP endpoint

| Environment | URL |
|---|---|
| Local | `http://localhost:8080/mcp/` |
| DataRobot | `https://<datarobot-endpoint>/deployments/<deployment-id>/directAccess/mcp/` |

## API keys

Remote connections require a DataRobot API token as a Bearer token:

```
Authorization: Bearer <your-datarobot-api-token>
```

See [DataRobot API key documentation](https://docs.datarobot.com/en/docs/get-started/acct-mgmt/acct-settings/api-key-mgmt.html) for how to create or retrieve your token.

## Documentation

| Document | Description |
|---|---|
| [MCP client setup](mcp_client_setup.md) | Configure Cursor, VS Code, and Claude Desktop |
| [Server architecture](mcp_server_architecture.md) | Project structure and full configuration reference |
| [Dynamic tool registration](dynamic_tool_registration.md) | Turn DataRobot deployments into tools automatically |
| [Custom tools](custom_tools.md) | Author domain-specific tools |
| [Deployment info tools](deployment_info_tools.md) | Query deployment features and build prediction datasets |

## Development

### Lint and format

```bash
task lint
```

### Run tests

```bash
task test
```

## Troubleshooting

### Server does not start

- Confirm `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT` are set in `.env`.
- Run `uv sync --all-extras` to ensure all dependencies are installed.

### MCP client cannot connect

- Verify the server is running: `curl http://localhost:8080/mcp/`
- Check MCP client logs (VS Code: Output panel → MCP; Cursor: MCP logs pane).
- Confirm the URL in your client config matches the server address and port.

### Tools are not appearing in the client

- Restart the MCP client after changing its configuration.
- Check server logs in the terminal where `task dev` is running.

### Dynamic tools are not registering

- Confirm the deployment is tagged with `tool` (both tag name and value).
- Confirm the deployment is active.
- See [dynamic tool registration](dynamic_tool_registration.md) for deployment-type-specific requirements.

## Best practices

- **Keep `.env` out of version control**&mdash;It is already in `.gitignore`. Never commit API tokens.
- **Write descriptive tool docstrings**&mdash;LLMs use docstrings to decide which tool to call. Write as if explaining the tool to a non-technical user.
- **Use type hints for all tool parameters**&mdash;FastMCP generates the MCP tool schema from Python type annotations; missing or incorrect types cause runtime errors.
- **Tag deployments consistently**&mdash;Use a naming convention for deployment tags so dynamic registration produces predictable tool names.
- **Enable OpenTelemetry in production**&mdash;Set `OTEL_ENABLED=true` to trace tool calls through the DataRobot monitoring UI.
- **Anti-pattern: returning raw exceptions to the client**&mdash;Catch specific exceptions in tool implementations and return structured error messages; unhandled exceptions expose internal details.
