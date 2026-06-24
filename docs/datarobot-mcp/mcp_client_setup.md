# MCP client setup

This guide explains how to connect common MCP clients to your DataRobot MCP server during local development and after deployment to DataRobot.
It includes:

- Cursor, VS Code, and Claude Desktop setup
- local and deployed connection examples
- authentication guidance for DataRobot direct-access endpoints
- security practices for API tokens and client configuration
- verification steps
- troubleshooting tips

## Table of contents

- [Prerequisites](#prerequisites)
- [Security and API tokens](#security-and-api-tokens)
- [Quick start](#quick-start)
  - [Cursor](#cursor)
  - [VS Code](#vs-code)
  - [Claude Desktop](#claude-desktop)
- [Use multiple environments](#use-multiple-environments)
- [Verify the connection](#verify-the-connection)
- [Troubleshooting](#troubleshooting)
- [Advanced features](#advanced-features)
- [Additional resources](#additional-resources)

## Prerequisites

Before you begin, make sure you have:

- A [running MCP server](../README.md#run-locally) (locally or deployed to DataRobot)
- Your [DataRobot API token](../README.md#add-api-credentials) (for remote connections)
- The [MCP endpoint URL](../README.md)

By default, this template serves MCP locally at `http://localhost:8080/mcp/`. If you set `MCP_SERVER_PORT`, replace `8080` in the examples below with your configured port.

For more information about DataRobot API keys, see the [DataRobot API keys documentation](https://docs.datarobot.com/en/docs/get-started/acct-mgmt/acct-settings/api-key-mgmt.html).

## Security and API tokens

Treat your DataRobot API key like a password.

- **Do not hardcode real keys** in examples, screenshots, chat logs, or source control. Use placeholders in docs and samples; store real values separately.
- **Prefer prompting or indirect configuration** so the key is not sitting in plain text when avoidable:
  - **VS Code**: use [input variables](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration#_input-variables-for-sensitive-data) (`promptString` with `"password": true`). VS Code prompts once and stores the value for later use (see the deployed VS Code example below).
  - **Cursor**: use [config interpolation](https://cursor.com/docs/context/mcp) with `${env:VAR}` in `headers` so the token lives in your environment, not in `mcp.json` (see the deployed Cursor example below).
- **Protect client config files** on disk: restrict permissions where applicable (for example `chmod 600` on Unix-like systems for files that contain secrets).
- **Use least privilege**: create keys with only the access your integration needs, and rotate or revoke a key if it may have been exposed.
- **Project vs user config**: if you use a project-level `.vscode/mcp.json` or `.cursor/mcp.json`, avoid committing secrets. Use user-level configuration, `inputs`, or environment variables instead.

For remote connections, DataRobot expects `Authorization: Bearer <token>`. When the client supports custom headers, also send `x-datarobot-api-key` with the same key value.

## Quick start

In the examples below, replace:

- `[YOUR_DATA_ROBOT_ENDPOINT]` with your DataRobot endpoint
- `[YOUR_DEPLOYMENT_ID]` with your deployment ID

For clients that read the token from the environment (Cursor), set `DATAROBOT_API_TOKEN` to your API key in the environment used to start the editor, or export it in your shell profile. For VS Code input-based setup, you will be prompted for the key when the server first starts.

### Cursor

Edit `~/.cursor/mcp.json`.

#### Local MCP server

```json
{
  "mcpServers": {
    "datarobot-local": {
      "url": "http://localhost:8080/mcp/"
    }
  }
}
```

#### Deployed MCP server

Use [config interpolation](https://cursor.com/docs/context/mcp) so the API key is not stored in `mcp.json`. Set `DATAROBOT_API_TOKEN` in the environment before starting Cursor (for example export it in your shell profile, or launch Cursor from a terminal session where it is already set).

```json
{
  "mcpServers": {
    "datarobot-production": {
      "url": "https://[YOUR_DATA_ROBOT_ENDPOINT]/deployments/[YOUR_DEPLOYMENT_ID]/directAccess/mcp/",
      "headers": {
        "Authorization": "Bearer ${env:DATAROBOT_API_TOKEN}",
        "x-datarobot-api-key": "${env:DATAROBOT_API_TOKEN}"
      }
    }
  }
}
```

After you update the file:

1. Restart Cursor.
2. Ask the cursor AI "What MCP tools are available?"

### VS Code

Open your MCP configuration with **MCP: Open User Configuration** (or edit `.vscode/mcp.json` for workspace scope). VS Code expects `servers` at the top level of `mcp.json`; see the [MCP configuration reference](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration).

Avoid hardcoding API keys. For deployed servers, use [input variables](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration#_input-variables-for-sensitive-data) so VS Code prompts for the key (with optional masked input) instead of storing it verbatim in the file.

#### Local MCP server

```json
{
  "servers": {
    "datarobot-local": {
      "type": "http",
      "url": "http://localhost:8080/mcp/"
    }
  }
}
```

#### Deployed MCP server

The first time this server starts, VS Code prompts for your DataRobot API key. The value is stored securely for later sessions (see VS Code documentation for where and how).

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "datarobot-api-key",
      "description": "DataRobot API key (direct access / MCP)",
      "password": true
    }
  ],
  "servers": {
    "datarobot-production": {
      "type": "http",
      "url": "https://[YOUR_DATA_ROBOT_ENDPOINT]/deployments/[YOUR_DEPLOYMENT_ID]/directAccess/mcp/",
      "headers": {
        "Authorization": "Bearer ${input:datarobot-api-key}",
        "x-datarobot-api-key": "${input:datarobot-api-key}"
      }
    }
  }
}
```

After you update the file:

1. Restart VS Code, or reload the window with `Cmd+Shift+P` -> `Developer: Reload Window`.
2. Open the Output panel and check the MCP-related output.

### Claude Desktop

Claude Desktop uses the `mcp-remote` proxy for HTTP-based MCP servers, so Node.js must be installed first.

1. Install Node.js if it is not already installed.

```bash
# macOS
brew install node

# Or download Node.js from https://nodejs.org/
```

2. Edit `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or the equivalent path on your OS.

#### Local MCP server

```json
{
  "mcpServers": {
    "datarobot-local": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "http://localhost:8080/mcp/",
        "--transport",
        "http"
      ]
    }
  }
}
```

#### Deployed MCP server

Keep the bearer token out of the `args` array. Set `AUTH_HEADER` to `Bearer <your-api-key>` in the `env` block. That value is still sensitive: treat `claude_desktop_config.json` like a secrets file (strict file permissions, do not commit it, rotate the key if the file is ever copied or shared).

```json
{
  "mcpServers": {
    "datarobot-production": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://[YOUR_DATA_ROBOT_ENDPOINT]/deployments/[YOUR_DEPLOYMENT_ID]/directAccess/mcp/",
        "--header",
        "Authorization: ${AUTH_HEADER}",
        "--transport",
        "http"
      ],
      "env": {
        "AUTH_HEADER": "Bearer [YOUR_DATA_ROBOT_API_KEY]"
      }
    }
  }
}
```

Replace `[YOUR_DATA_ROBOT_API_KEY]` once when you edit the file, or manage the value outside version control (for example a private copy of the config) if you share your dotfiles.

After you update the file:

1. Completely quit Claude Desktop.
2. Restart the application.
3. Ask the Claude Desktop AI "What tools do you have access to?"

## Use multiple environments (optional)

You can define multiple MCP servers in the same client configuration, such as local, staging, and production. This is useful when you want to test locally before switching to a deployed server.

*Example for Cursor*:

```json
{
  "mcpServers": {
    "local": {
      "url": "http://localhost:8080/mcp/"
    },
    "production": {
      "url": "https://[YOUR_DATA_ROBOT_ENDPOINT]/deployments/[YOUR_DEPLOYMENT_ID]/directAccess/mcp/",
      "headers": {
        "Authorization": "Bearer ${env:DATAROBOT_API_TOKEN}",
        "x-datarobot-api-key": "${env:DATAROBOT_API_TOKEN}"
      }
    }
  }
}
```

## Verify the connection

After you configure your client, verify both the server and the client connection.

### Verify the server

1. Check that the server is running:

   ```bash
   curl http://localhost:8080/
   ```

   Expected result: a JSON health response, such as `{"status": "healthy", "message": "DataRobot MCP Server is running"}`.

2. Check the MCP endpoint:

   ```bash
   curl http://localhost:8080/mcp/
   ```

   Expected result: an MCP protocol response.

### Verify each client

#### Cursor

1. Open Cursor.
2. Open the Command Palette with `Cmd+Shift+P` on macOS or `Ctrl+Shift+P` on Windows and Linux.
3. Search for MCP-related commands.
4. Ask, "What MCP tools are available?"
5. Confirm that Cursor lists tools from your MCP server.

#### VS Code

1. Open VS Code.
2. Open `View -> Output`.
3. Select the MCP-related output, if available.
4. Look for successful connection messages.
5. Use an AI feature and ask about available tools.

#### Claude Desktop

1. Open Claude Desktop.
2. Review `~/Library/Logs/Claude/mcp*.log` on macOS, or the equivalent log path on your OS.
3. Look for a successful connection message.
4. Ask, "What tools do you have access to?"

## Troubleshooting

### Check client logs

If the connection test fails, review the client logs first:

- Cursor: `View -> Output`, then select `MCP Logs`
- VS Code: `View -> Output`, then select the MCP-related output
- Claude Desktop: `~/Library/Logs/Claude/mcp*.log`

### Server issues

If the server does not start:

```text
Port 8080 already in use?
  Yes -> stop the process using that port
  No  -> check dependencies and environment variables

Missing dependencies?
  Yes -> run `task install`
  No  -> review the startup logs

Invalid API token?
  Yes -> generate a new token in DataRobot
  No  -> check your `.env` file
```

If the server starts but returns errors:

- review the server logs for the exact error
- confirm that `DATAROBOT_API_TOKEN` is valid
- confirm that `DATAROBOT_ENDPOINT` is correct
- make sure the required environment variables are set

### Client connection issues

If the client cannot connect:

- make sure the server is running
- verify the configured URL
- confirm that the client was restarted after the config change
- check for firewall or network restrictions

Use these URL patterns:

- local: `http://localhost:8080/mcp/`
- deployed: `https://<your-endpoint>/deployments/<id>/directAccess/mcp/`

### Authentication issues

For DataRobot direct-access endpoints, use `Authorization: Bearer <token>`. For clients that support custom headers directly, also include `x-datarobot-api-key` with the same API key value.

If authentication fails:

- confirm that the API token is valid
- confirm that the `Bearer` header is formatted correctly
- confirm that the deployment ID is correct
- make sure your account has access to the deployment
- **Cursor**: confirm `DATAROBOT_API_TOKEN` is set in the environment of the Cursor process (fully quit and relaunch from a shell where it is exported, if needed)
- **VS Code**: confirm you completed the input prompt for `${input:datarobot-api-key}` (or reset inputs if you entered the wrong value; see VS Code MCP documentation)
- avoid pasting live tokens into chat, tickets, or screen shares; rotate the key if it may have leaked

### Claude Desktop issues

If Claude Desktop cannot launch `mcp-remote`:

- make sure Node.js is installed
- run `node --version`
- run `npx mcp-remote@latest --version`
- make sure `npx` is available in your `PATH`

### Quick diagnostic commands

Test your API token (run only in a trusted shell; avoid echoing the token or logging it):

```bash
curl -H "Authorization: Bearer $DATAROBOT_API_TOKEN" \
  "$DATAROBOT_ENDPOINT/api/v2/projects/" | head -1
```

Check whether port 8080 is already in use:

```bash
lsof -i :8080
```

## Advanced features

Most users can skip this section. These settings are useful when you need advanced deployment or observability behavior.

### Dynamic tool registration

Use this feature when you want the MCP server to discover DataRobot deployments and register them as tools automatically.

```bash
MCP_SERVER_REGISTER_DYNAMIC_TOOLS_ON_STARTUP=true
```

For details, see the [dynamic tool registration guide](./dynamic_tool_registration.md).

### Dynamic prompt registration

Use this feature when you want the MCP server to discover DataRobot prompts and register them automatically.

```bash
MCP_SERVER_REGISTER_DYNAMIC_PROMPTS_ON_STARTUP=true
```

### OpenTelemetry tracing

Use this feature when you need distributed tracing for debugging or observability.

```bash
OTEL_ENABLED=true
OTEL_COLLECTOR_BASE_URL=https://your-otel-endpoint
OTEL_ENTITY_ID=your-entity-id
```

### Feature flag validation

If your deployment depends on specific DataRobot features, add feature flag files under `infra/feature_flags/` so deployment fails early when required capabilities are unavailable.

## Additional resources

- [FastMCP documentation](https://github.com/jlowin/fastmcp)
- [Model Context Protocol specification](https://modelcontextprotocol.io/)
- [Cursor MCP documentation](https://docs.cursor.com/)
- [Claude Desktop documentation](https://www.anthropic.com/claude/desktop)