# MCP server

An MCP server is a utility that allows the agent to access tools.
The template is configured to automatically connect the agent with an MCP server both locally and in a deployed setting.
The MCP server in this template is provided by the [DataRobot MCP AF Component](https://github.com/datarobot-community/af-component-datarobot-mcp) (App Framework).

## Optional co-deployment

The MCP component is optional. When the `mcp_server/` module is present in your project (the default Agentic Starter layout), infrastructure auto-wires MCP runtime parameters by importing `mcp_custom_model_runtime_parameters` from the conventional module name `mcp_server`.

| Layout | Behavior |
|---|---|
| `mcp_server/` present (default) | Pulumi loads MCP settings from `mcp_server` automatically. Deploy includes the MCP custom model alongside the agent. |
| No `mcp_server/` module | Infrastructure falls back to environment variables (`MCP_DEPLOYMENT_ID`, `EXTERNAL_MCP_URL`, and related `EXTERNAL_MCP_*` settings). |

To use an external or pre-deployed MCP server without bundling `mcp_server/` in the application, remove or omit that module and set `MCP_DEPLOYMENT_ID` or `EXTERNAL_MCP_URL` in `.env` instead. See [Testing against remote servers](#testing-against-remote-servers) below.

To add the MCP component to a project that does not include it, follow the [af-component-datarobot-mcp getting started guide](https://github.com/datarobot-community/af-component-datarobot-mcp#getting-started).

## Testing against remote servers

When testing locally, the MCP server connects to a local instance running at `http://localhost:9000` by default (see [Ports reference](../README.md#ports-reference) for all port information).
To modify the port, set the `MCP_SERVER_PORT` environment variable in your `.env` file.

To test against remote MCP servers:

1. Set the `MCP_DEPLOYMENT_ID` environment variable to test against a deployed MCP server in DataRobot.
2. Set the `EXTERNAL_MCP_URL` environment variable to connect to an external MCP server endpoint (for example: `https://example.com/mcp`).
  
  > [!NOTE]
  > DataRobot bearer tokens and OAuth context are not forwarded to external MCP servers.
  > To send custom headers, set the `EXTERNAL_MCP_HEADERS` environment variable to a JSON string (e.g., `'{"Authorization":"Bearer token123","X-Custom-Header":"value"}'`); it will be parsed using `json.loads()`.
  > To change the transport for MCP server, set the `EXTERNAL_MCP_TRANSPORT` environment variable to `sse` or `streamable-http` (default).

3. When running `dr run deploy`, the project automatically deploys the MCP server from your project when `mcp_server/` is present, which takes precedence over MCP servers configured via environment variables for testing purposes.
