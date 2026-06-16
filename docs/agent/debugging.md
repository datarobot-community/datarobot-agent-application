# Debugging agents

This guide covers how to debug agent code during local development using the CLI, VS Code, and PyCharm. For the official DataRobot debugging documentation, see [Debug agents in VS Code](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-debugging-vscode.html) and [Debug agents in PyCharm](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-debugging-pycharm.html).

## Prerequisites

- Completed `dr start` (creates `.env` and the agent virtual environment).
- `.env` file with `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT` configured.
- Dependencies installed: `dr task run agent:install`.

## Development server

All debugging approaches require the agent development server. The server is a local DRUM instance that loads your agent code and serves it on an HTTP endpoint (default port `8842`).

The entry point is `agent/dev.py`, which starts a `PredictionServer` with `targetType: agenticworkflow`. The server reads `.env` for configuration and loads hooks from `agent/custom.py`.

### Start manually

Start the server in one terminal and keep it running:

```sh
dr task run agent:dev
```

Then send requests from a second terminal using the CLI.

### DRAgent mode

When `ENABLE_DRAGENT_SERVER=true` is set, the development server runs `nat dragent serve` instead of DRUM. The Taskfile forwards CLI commands directly to `nat dragent run` or `nat dragent query`.

## Testing with the CLI

The agent CLI (`agent/cli.py`) provides commands for testing against both local and deployed agents.

### Local execution

Submit a prompt to a running local development server:

```sh
task agent:cli -- execute --user_prompt "Artificial Intelligence"
```

With a structured JSON prompt:

```sh
task agent:cli -- execute --user_prompt '{"topic": "Generative AI"}'
```

With streaming enabled:

```sh
task agent:cli -- execute --user_prompt "Artificial Intelligence" --stream
```

Auto-start the dev server for a single test (starts and stops automatically):

```sh
task agent:cli START_DEV=1 -- execute --user_prompt "Artificial Intelligence"
```

With a prompt from a text file:

```sh
task agent:cli -- execute --file "example-prompt.txt"
```

### DRAgent execution

When `ENABLE_DRAGENT_SERVER=true`, `execute` runs the workflow directly in-process via `nat dragent run` without needing a running server:

```sh
task agent:cli -- execute --user_prompt "Artificial Intelligence"
task agent:cli -- execute --file "example-prompt.txt"
```

### Deployed agent execution

Query a deployed agent:

```sh
task agent:cli -- execute-deployment --user_prompt "Artificial Intelligence" --deployment_id DEPLOYMENT_ID
```

### CLI options

| Flag | Description |
|---|---|
| `--user_prompt` | Text or JSON prompt to send. |
| `--completion_json` | Path to a JSON file with full chat completion params. Not supported with dragent mode. |
| `--file` | Path to a text file whose contents are used as the prompt. Dragent mode only. |
| `--stream` | Enable streaming response. Not supported with dragent mode. |
| `--show_output` | Display full response inline. Not supported with dragent mode. |
| `--deployment_id` | Target a deployed agent instead of local. |

## Debugging in VS Code

This repository includes a pre-configured launch configuration in `.vscode/launch.json`.

### Setup

1. Open the repository in VS Code.
2. Ensure the Python extension is installed.
3. Select the agent interpreter: press `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P`, run **Python: Select Interpreter**, and choose `agent/.venv/bin/python`.

### Launch configuration

The included `.vscode/launch.json` is already configured:

```json
{
    "name": "Python Debugger: Agent",
    "type": "debugpy",
    "request": "launch",
    "program": "${workspaceFolder}/agent/dev.py",
    "console": "integratedTerminal",
    "envFile": "${workspaceFolder}/.env",
    "python": "${workspaceFolder}/agent/.venv/bin/python",
    "justMyCode": false,
    "cwd": "${workspaceFolder}/agent"
}
```

### Debug workflow

1. Set breakpoints in your agent code (e.g. `agent/agent/myagent.py`).
2. Open the **Run and Debug** view and select **Python Debugger: Agent**.
3. Press **F5** to start the development server under the debugger.
4. Wait for the `Running development server on http://localhost:8842` message.
5. In a separate terminal, run a CLI command:
   ```sh
   task agent:cli -- execute --user_prompt "Artificial Intelligence"
   ```
6. VS Code pauses at your breakpoints. Use the debug toolbar to step through code, inspect variables, and evaluate expressions.

`justMyCode` is set to `false` so you can step into `datarobot_genai` and framework code when needed.

## Debugging in PyCharm

This repository includes a pre-configured **Run Agent** run/debug configuration in `.idea/runConfigurations/Run_Agent.xml`.

### Setup

1. Open the repository in PyCharm.
2. Go to **Settings > Python > Interpreter** and select the agent virtual environment: `agent/.venv/bin/python`.

### Debug workflow

1. Set breakpoints in your agent code (e.g. `agent/agent/myagent.py`).
2. Select **Run Agent** from the configuration dropdown.
3. Click the **Debug** icon (or press **Shift+F9**).
4. Wait for the development server to start.
5. In a separate terminal, run:
   ```sh
   task agent:cli -- execute --user_prompt "Artificial Intelligence"
   ```
6. PyCharm pauses at your breakpoints. Use the **Threads & Variables** pane to inspect state and the **Evaluate Expression** dialog to test code in context.

The **Run Agent** configuration points to `agent/dev.py`, sets the working directory to `agent/`, and loads environment variables from `.env`.

## Enable verbose logging

Set `verbose=True` when instantiating `MyAgent` to get detailed logging of agent execution, LLM calls, and tool invocations. In the template, verbosity defaults to `True` in `custompy_adaptor` (via `completion_create_params`).

You can also enable verbose mode via the CLI completion JSON by adding `"verbose": true` to the `extra_body` field.

### NAT log level (DRAgent mode)

When running in DRAgent mode (`ENABLE_DRAGENT_SERVER=true`), control NAT's log verbosity with the `NAT_LOG_LEVEL` environment variable:

```sh
export NAT_LOG_LEVEL=DEBUG
dr task run agent:dev
```

Supported values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Defaults to `INFO` if not set.

## Common issues

### Development server not starting

**Symptom:** `task agent:dev` fails or the server doesn't respond.

**Fix:** Verify `.env` exists with `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT`. Re-run `dr task run agent:install` to ensure dependencies are up to date.

### Breakpoints not hit

**Symptom:** The CLI command completes but the debugger never pauses.

**Fix:**
- Ensure you started the server in **Debug** mode, not regular Run.
- Confirm the breakpoint is on a line that actually executes for your prompt.
- Re-run the CLI command after the debugger is fully attached&mdash;the dev server handles one request at a time.

### Import errors in `myagent.py`

**Symptom:** Imports to files in the same directory fail silently in DRUM.

**Fix:** Use relative imports (e.g. `from .tools import my_tool`) instead of package imports (e.g. `from agent.tools import my_tool`).

### Wrong Python interpreter

**Symptom:** `ModuleNotFoundError` for `datarobot_genai` or framework packages.

**Fix:** Ensure your IDE is using `agent/.venv/bin/python` and not a system Python. Re-run `dr task run agent:install` if the virtual environment was recreated.

### Environment variables not loaded

**Symptom:** Agent fails with missing `DATAROBOT_API_TOKEN`.

**Fix:** Confirm `envFile` in VS Code or **Paths to ".env" files** in PyCharm points to the `.env` at the repository root.

## Debugging deployed agents

For agents deployed to DataRobot, you can:

- **View logs**&mdash;on the deployment's **Activity log** tab, click **Logs** to see OpenTelemetry-format logs with level filtering and time-period selection.
- **View traces**&mdash;on the **Service health** tab, click **Show tracing** to see end-to-end request traces including LLM calls, tool invocations, and agent actions.
- **Test via CLI**&mdash;use `task agent:cli -- execute-deployment` to send test prompts to a deployed agent and inspect the response.

For more on deployed agent observability, see the [DataRobot tracing documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html).
