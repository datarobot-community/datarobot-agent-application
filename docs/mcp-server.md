# Connect your agent to MCP tools

The agent can use tools served by any [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server.
This template does not include an MCP server: you run one separately and tell the agent where it is.

To build your own, start from the [DataRobot MCP template](https://github.com/datarobot-community/datarobot-mcp-template).

> [!NOTE]
> Projects created from earlier versions of this template include an MCP server in `mcp_server/`.
> Newer versions of this template remove it, and a deployed app's next deploy stops until you confirm. See [Move your MCP server out of the Agentic Starter](mcp-migration.md).

## Point the agent at your server

Set one of these in `.env`:

| Your MCP server | Setting |
|---|---|
| The [DataRobot Global MCP](#use-the-datarobot-global-mcp), for the built-in DataRobot tools | `EXTERNAL_MCP_URL` and `EXTERNAL_MCP_HEADERS` |
| Deployed in DataRobot as a custom model (the MCP template's default) | `MCP_DEPLOYMENT_ID` |
| Deployed in DataRobot on the Workload API | `MCP_WORKLOAD_ID` |
| Any other MCP endpoint | `EXTERNAL_MCP_URL`, and `EXTERNAL_MCP_HEADERS` if the server needs authentication |
| Running on your machine | `MCP_SERVER_PORT` |

`dr run deploy` passes all of these except `MCP_SERVER_PORT` to the deployed agent.
The agent documentation's [MCP tools](agent/mcp.md) page covers which setting wins when several are set, what the agent sends to each kind of server, servers that require Okta cross-application access (XAA), and troubleshooting.

## Use the DataRobot Global MCP

For the built-in DataRobot tools, you don't need an MCP server of your own: DataRobot runs the Global MCP on your instance. For the tools it offers, see [MCP server overview](https://docs.datarobot.com/en/docs/agentic-ai/agentic-mcp/agentic-mcp-overview.html) in the DataRobot docs. Set in `.env`:

```sh
# Your DATAROBOT_ENDPOINT followed by /genai/globalmcp/mcp
EXTERNAL_MCP_URL=https://app.datarobot.com/api/v2/genai/globalmcp/mcp
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <your DataRobot API key>"}'
```

The agent doesn't send its DataRobot credentials to an `EXTERNAL_MCP_URL`, so the API key goes in `EXTERNAL_MCP_HEADERS`. The agent gets every tool the Global MCP has. To give it only some, list their names, separated by commas, in the `x-datarobot-mcp-tools` header:

```sh
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <your DataRobot API key>", "x-datarobot-mcp-tools": "<tool name>,<tool name>"}'
```

See [Built-in tools: use the DataRobot Global MCP](mcp-migration.md#built-in-tools-use-the-datarobot-global-mcp) for which tools to move there.

## Use an MCP server deployed in DataRobot

1. Deploy the [DataRobot MCP template](https://github.com/datarobot-community/datarobot-mcp-template) with `task deploy`.
2. Read its outputs:

   ```sh
   cd infra && uv run pulumi stack output --json
   ```

3. Copy the `... [dr_mcp] Deployment Id` value into this project's `.env`:

   ```sh
   MCP_DEPLOYMENT_ID=<deployment id>
   ```

   If you deployed the server to the Workload API, copy `... [dr_mcp] Workload Id` into `MCP_WORKLOAD_ID` instead.

4. Run `dr run dev` and ask the agent which tools it has.
5. Run `dr run deploy`.

## Run an MCP server locally next to the agent

The MCP template serves on port 8080 by default, which this project's web app also uses. To run it on another port:

1. In the MCP template project's `.env`, set:

   ```sh
   MCP_SERVER_PORT=9000
   ```

2. Start it with `task dev` in that project.
3. In this project's `.env`, set:

   ```sh
   MCP_SERVER_PORT=9000
   ```

4. Leave `MCP_WORKLOAD_ID`, `MCP_DEPLOYMENT_ID`, and `EXTERNAL_MCP_URL` unset in this project, because they take precedence over `MCP_SERVER_PORT`.

## Keep an MCP server inside this project

You can still run an MCP server from this repository and deploy it together with the agent:

1. Add the MCP component:

   ```sh
   dr component add https://github.com/datarobot-community/af-component-datarobot-mcp.git
   ```

   Keep the default app name, `mcp_server`, and answer `9000` for the development port.

2. Add it to `.taskfile-data.yaml` so that `dr run dev` starts it:

   ```yaml
     - name: mcp_server
       port: 9000
   ```

`dr run deploy` then deploys the server and connects the agent to it.
How that connection works, and when it does not apply, is described in [MCP server deployed with the agent](agent/mcp.md#mcp-server-deployed-with-the-agent).
