# Agent

The agent component is the core of the application. It defines the AI workflow that processes user requests, invokes tools, and produces responses. Agents integrate with DataRobot for LLM access, tool management, and deployment, and can be built using multiple agentic frameworks.

For the official DataRobot documentation on agent components, see [Agent components](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-overview.html).

| Section | Description |
|---|---|
| [Features](#features) | Key capabilities of the agent component. |
| [Agent file structure](#agent-file-structure) | Important files and their organization. |
| [Functions and hooks](#functions-and-hooks-custompy) | Mandatory functions and integration hooks for agent operation. |
| [Agent class implementation](#agent-class-implementation-myagentpy) | Agent class and its framework-specific implementation. |
| [Tool integration](#tool-integration) | How agents use tools via MCP, workflow tools, and custom local tools. |
| [Configuration](#configuration) | Agent configuration management. |
| [Front servers](#front-servers) | The two supported front server implementations: DRUM and DRAgent. |
| [Agent types](#agent-types) | Supported agent frameworks and links to examples. |
| [Debugging](./debugging.md) | Debug agents locally using the CLI, VS Code, and PyCharm. |
| [Further reading](#further-reading) | Links to official DataRobot docs for troubleshooting, tracing, global tools, and more. |

## Features

### AG-UI (Agent-User Interaction Protocol)

All agents use [AG-UI](https://docs.ag-ui.com/introduction) as the primary streaming interface. AG-UI is an open, event-based protocol that defines a standard set of event types — lifecycle, text messages, tool calls, state management, and reasoning — that agents emit during execution. This enables the frontend to render real-time progress, tool invocations, and final output consistently across all frameworks.

See the [AG-UI integration guide](./ag-ui.md) for details on each event type and how they are used in this template.

### Agent-to-Agent (A2A)

Agents can expose themselves as A2A servers and connect to remote agents via the agent-to-agent protocol. This requires the DRAgent front server (`ENABLE_DRAGENT_SERVER=true`). See [Agent2Agent](./agent2agent.md) for configuration and usage.

## Agent file structure

The agent is implemented in the `agent/` directory. The inner `agent/agent/` package contains the code you edit; the outer files provide infrastructure for running and deploying the agent.

```
agent/
├── agent/                  # Agent Python package (your code goes here)
│   ├── __init__.py         # Package exports: MyAgent, Config, custompy_adaptor
│   ├── myagent.py          # Agent definition (framework-specific)
│   ├── config.py           # Configuration management
│   ├── register.py         # DRAgent/NAT registration (framework-specific)
│   └── workflow.yaml       # Declarative workflow config (framework-specific)
├── tests/                  # Agent tests
│   ├── conftest.py
│   ├── test_agent.py
│   └── ...
├── custom.py               # DRUM integration hooks (load_model, chat)
├── cli.py                  # CLI for local testing and deployment validation
├── dev.py                  # Local development server
├── pyproject.toml          # Python dependencies and project metadata
├── Taskfile.yml            # Task runner definitions (install, lint, test)
└── uv.lock                 # Dependency lockfile
```

| File | Description |
|---|---|
| `agent/myagent.py` | **Framework-specific.** Contains the main agent implementation. Defines the `MyAgent` class and a `custompy_adaptor` function for DRUM compatibility. The implementation varies by framework — see [Agent types](#agent-types) for details. |
| `agent/config.py` | Manages configuration loading from environment variables, runtime parameters, and DataRobot credentials. |
| `agent/register.py` | **Framework-specific.** NAT registration module used by the DRAgent front server. Wires LLM, MCP tools, workflow tools, and the agent together. |
| `agent/workflow.yaml` | **Framework-specific.** Declarative workflow configuration for the DRAgent front server: front-end type, A2A metadata, LLM component, and workflow type. |
| `custom.py` | Implements DataRobot DRUM integration hooks (`load_model`, `chat`) for agent execution. |
| `cli.py` | CLI for testing the agent locally and validating deployments. |
| `dev.py` | Local development prediction server using DRUM. |

**Note:** The files `myagent.py`, `register.py`, and `workflow.yaml` are generated from framework-specific templates during project setup. Their content depends on the chosen agent framework (LangGraph, CrewAI, LlamaIndex, NAT, or Base).

## Functions and hooks (`custom.py`)

The `custom.py` file at the root of the `agent/` directory contains the required functions that DataRobot DRUM calls to execute the agent. These hooks connect the DataRobot runtime with the agent's logic.

| Hook | Description |
|---|---|
| `load_model()` | One-time initialization function called when DataRobot starts the agent. |
| `chat()` | Main execution function called for each user interaction/chat message. |

### `load_model()` hook

Called once to initialize the agent runtime. Sets up a `ThreadPoolExecutor` and an `asyncio` event loop to bridge DRUM's synchronous interface with the agent's async code.

```python
def load_model(code_dir: str) -> tuple[ThreadPoolExecutor, asyncio.AbstractEventLoop]:
    thread_pool_executor = ThreadPoolExecutor(1)
    event_loop = asyncio.new_event_loop()
    thread_pool_executor.submit(asyncio.set_event_loop, event_loop).result()
    return (thread_pool_executor, event_loop)
```

### `chat()` hook

The main entry point for agent execution. DataRobot calls this function every time a user sends a message. It accepts OpenAI-compatible completion parameters and returns either a single response or a streaming iterator.

```python
def chat(
    completion_create_params: CompletionCreateParams,
    load_model_result: tuple[ThreadPoolExecutor, asyncio.AbstractEventLoop],
    **kwargs: Any,
) -> Union[CustomModelChatResponse, Iterator[CustomModelStreamingResponse]]:
    ...
```

The `chat()` hook handles:
- Loading the agent `Config` for MCP runtime parameters.
- Resolving authorization context for downstream tools and services.
- Forwarding DataRobot-specific headers (`x-datarobot-*`) to the agent and MCP server.
- Routing to streaming or non-streaming execution based on the request.

## Agent class implementation (`myagent.py`)

The `myagent.py` file contains the agent's core logic. The implementation depends on your chosen framework, but all frameworks follow the same pattern: define the agent using native framework primitives, then wrap it into a `MyAgent` class that DataRobot can invoke.

Each framework uses a factory helper from `datarobot_genai` to generate `MyAgent`:

| Framework | Factory | Input |
|---|---|---|
| LangGraph | `datarobot_agent_class_from_langgraph` | `graph_factory` function + `prompt_template` |
| CrewAI | `datarobot_agent_class_from_crew` | `Crew` + agents + tasks + `kickoff_inputs` |
| LlamaIndex | `datarobot_agent_class_from_llamaindex` | `AgentWorkflow` + agents + `extract_response_text` |
| NAT | Direct subclass of `NatAgent` | `workflow.yaml` path |
| Base | Direct subclass of `BaseAgent` | Manual `invoke()` implementation |

The `custompy_adaptor` function in `myagent.py` bridges the `MyAgent` class with DRUM's `chat()` hook by creating an MCP config, resolving the LLM, instantiating the agent, and invoking it via `agent_chat_completion_wrapper`.

**Important:** The name `MyAgent` must not be changed&mdash;it is referenced by the framework infrastructure.

See the framework-specific documentation for detailed implementation guides:

- [Base](./frameworks/base.md)&mdash;manual `invoke()` with AG-UI events.
- [LangGraph](./frameworks/langgraph.md)&mdash;`StateGraph` with `create_agent` nodes.
- [CrewAI](./frameworks/crewai.md)&mdash;agents, tasks, and crews.
- [LlamaIndex](./frameworks/llamaindex.md)&mdash;`FunctionAgent` and `AgentWorkflow`.
- [NAT](./frameworks/nat.md)&mdash;fully declarative YAML configuration.

## Tool integration

Agents can use tools to extend their capabilities. Tools are injected at runtime from multiple sources — no static tool modules need to be defined in the repository.

### MCP tools

MCP tools are loaded from the MCP server via `mcp_tools_context()`. Each framework has its own MCP adapter in `datarobot_genai` (e.g. `datarobot_genai.langgraph.mcp`, `datarobot_genai.crewai.mcp`). The MCP server provides tools for DataRobot operations and can be extended with custom tools. See [MCP server](../mcp-server.md) for details.

### Workflow tools (DRAgent only)

When using the DRAgent front server, additional tools can be defined in `workflow.yaml` under `tool_names` and resolved by NAT at startup. This is primarily used for connecting to remote agents via A2A. See [Agent2Agent](./agent2agent.md).

### Custom local tools

To add custom tools directly in the agent, create tool functions in the `agent/agent/` directory using your framework's tool API and pass them into the agent definition. For example, with LangGraph:

```python
from langchain_core.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """Description of what the tool does."""
    return "result"
```

### Authorization context

The `resolve_authorization_context()` function from the `datarobot-genai` package is called in `custom.py` to automatically handle authentication for tools that require access tokens. This ensures tools can securely access external services using DataRobot's credential management system.

## Configuration

Agent configuration is managed by the `Config` class in `agent/config.py`, which extends `DataRobotAppFrameworkBaseSettings`. It loads values in the following priority order: environment variables (including runtime parameters), `.env` files, file secrets, then Pulumi output variables.

| Variable | Description | Default |
|---|---|---|
| `LLM_DEPLOYMENT_ID` | DataRobot LLM deployment ID. | `None` |
| `LLM_DEFAULT_MODEL` | Default LLM model identifier. | `datarobot/azure/gpt-5-mini-2025-08-07` |
| `USE_DATAROBOT_LLM_GATEWAY` | Route LLM calls through DataRobot gateway. | `false` |
| `MCP_DEPLOYMENT_ID` | Deployed MCP server ID. | `None` |
| `EXTERNAL_MCP_URL` | External MCP server URL. | `None` |
| `AGENT_PORT` | Local agent server port. | `8842` |

Values set to `SET_VIA_PULUMI_OR_MANUALLY` are automatically replaced with field defaults at startup.

For LLM configuration details, see [LLM configuration](../llm-configuration.md).

## Front servers

The agent component supports two front server implementations that serve the agent over HTTP. The front server is the runtime layer that receives incoming requests, invokes the agent, and returns responses.

### DRUM

**DRUM** (DataRobot User Model) is the traditional front server for custom models in DataRobot. It is the default and runs unless DRAgent is explicitly enabled.

- **Entry point**&mdash;`custom.py`, implements `load_model()` and `chat()` hooks.
- **Execution model**&mdash;synchronous. Uses a `ThreadPoolExecutor` to bridge async agent code into DRUM's sync interface.
- **Status**&mdash;stable, feature-complete. This is the production-tested path used in DataRobot deployments.
- **Streaming**&mdash;supported via a sync/async queue bridge that drains async events into a thread-safe queue consumed synchronously.

DRUM serves the agent as a DataRobot custom model, exposing an OpenAI-compatible chat completion API. The `custom.py` hooks (`load_model` and `chat`) follow the DataRobot [structured model hooks](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-overview.html) contract.

### DRAgent

**DRAgent** is the next-generation front server built on NAT (NeMo Agent Toolkit) and FastAPI. It is currently in active development.

- **Entry point**&mdash;`register.py` + `workflow.yaml`, uses NAT's declarative workflow registration.
- **Execution model**&mdash;fully asynchronous (native `async`/`await`).
- **Status**&mdash;experimental, in active development. Enabled via the `ENABLE_DRAGENT_SERVER` environment variable.
- **Streaming**&mdash;native async streaming via `DRAgentEventResponse`.

> [!IMPORTANT]
> When using DRAgent, the agent CLI is unavailable.

DRAgent enables features that are not available with DRUM:

- **Agent-to-Agent (A2A)**&mdash;expose your agent as an A2A server and connect to remote agents. See [Agent2Agent](./agent2agent.md).
- **Declarative workflow configuration**&mdash;define LLMs, tools, and agent connections in `workflow.yaml`.
- **NAT ecosystem**&mdash;access the full NeMo Agent Toolkit including NAT-provided LLM interfaces, function types, and tool integrations.

To enable DRAgent, set the following in your `.env` file:

```sh
ENABLE_DRAGENT_SERVER=true
```

When enabled locally, the Taskfile starts NAT with the `dragent_fastapi` front-end instead of DRUM. In deployed environments, the `ENABLE_DRAGENT_SERVER` runtime parameter is set automatically by the infrastructure.

> [!NOTE]
> DRAgent is experimental and currently under active development. Use at your own risk.

## Agent types

This template ships with a LangGraph-based agent by default, but the agent component supports multiple frameworks. Each framework uses a different approach to defining agents while following the same project structure, deployment pipeline, and file layout.

The three framework-specific files — `myagent.py`, `register.py`, and `workflow.yaml` — are generated from framework-specific templates during project setup. Their content depends on the chosen framework.

| Framework | `myagent.py` pattern | `workflow.yaml` type | Documentation |
|---|---|---|---|
| **LangGraph** | `datarobot_agent_class_from_langgraph` with `StateGraph` | `langgraph_agent` | [LangGraph agent](./frameworks/langgraph.md) |
| **CrewAI** | `datarobot_agent_class_from_crew` with `Crew` | `crewai_agent` | [CrewAI agent](./frameworks/crewai.md) |
| **LlamaIndex** | `datarobot_agent_class_from_llamaindex` with `AgentWorkflow` | `llamaindex_agent` | [LlamaIndex agent](./frameworks/llamaindex.md) |
| **NAT** | `MyAgent(NatAgent)` subclass | `per_user_tool_calling_agent` | [NAT agent](./frameworks/nat.md) |
| **Base** | `MyAgent(BaseAgent)` with manual `invoke()` | `base_agent` | [Base agent](./frameworks/base.md) |

All agent types use the same `datarobot_genai` package for LLM configuration, response formatting, and DataRobot service integration. The templates automatically include this package.

## Migrations

### 11.8.8 — New agent format

Starting with version 11.8.8, agent templates (except `base`) no longer require defining agents within a `MyAgent` class. They are now converted from their native framework primitives to `MyAgent` with a helper function. The LLM is also decoupled from the agent class. See the [changelog](../../CHANGELOG.md) and [af-component-agent#474](https://github.com/datarobot-community/af-component-agent/pull/474) for details.

Migration guides per framework:

| Framework | Migration guide |
|---|---|
| LangGraph | [migration-to-11.8.8-langgraph.md](./frameworks/migration-to-11.8.8-langgraph.md) |
| CrewAI | [migration-to-11.8.8-crewai.md](./frameworks/migration-to-11.8.8-crewai.md) |
| LlamaIndex | [migration-to-11.8.8-llamaindex.md](./frameworks/migration-to-11.8.8-llamaindex.md) |
| Base | [migration-to-11.8.8-base.md](./frameworks/migration-to-11.8.8-base.md) |
| NAT | [migration-to-11.8.8-nat.md](./frameworks/migration-to-11.8.8-nat.md) |

## Further reading

The following topics are covered in the official DataRobot documentation:

| Topic | Description |
|---|---|
| [Troubleshooting](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-troubleshooting.html) | Diagnose and resolve common issues with agent setup, deployment, LLM gateway, and imports. |
| [Implement tracing](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html) | Add custom OpenTelemetry tracing to agent tools for monitoring and debugging deployed agents. |
| [Deploy agentic tools](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tools.html) | Deploy global tools from the DataRobot Registry (search datasets, make predictions, render charts). |
| [DataRobot agentic skills](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-skills.html) | Install modular skill packages for coding agents (Cursor, Claude Code, Codex, and others). |
| [Agent authentication](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-authentication.html) | API tokens, OAuth 2.0, authorization context, and MCP server authentication. |
| [Add Python packages](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-python-packages.html) | Add dependencies via `uv`, runtime dependencies for fast iteration, and custom Docker images. |
| [Access request headers](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-request-headers.html) | Extract `X-Untrusted-*` headers in deployed agents for auth forwarding and request tracking. |

## Development

### Install dependencies

```sh
dr task run agent:install
```

> [!WARNING]
> When using a custom Docker context (`DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` is unset and an `agent/docker_context/` folder is present), modifying `pyproject.toml` or `uv.lock` triggers a full execution environment rebuild on the next deployment. This rebuild can take **10–20 minutes** depending on the number of dependencies. When using the default DataRobot execution environment (the default configuration), dependency changes do not trigger a rebuild.

### Run tests

```sh
dr task run agent:test
```

### Run linter

```sh
dr task run agent:lint
```

### Run locally

Start the full application (agent + backend + frontend):

```sh
dr run dev
```

Or run just the agent:

```sh
dr run agent:dev
```

### Test with CLI

Submit a test query to a running agent:

```sh
task agent:cli -- execute --user_prompt '{"topic":"Generative AI"}'
```

Auto-start the dev server for a single test:

```sh
task agent:cli START_DEV=1 -- execute --user_prompt '{"topic":"Generative AI"}'
```

### Validate a deployment

```sh
task agent:cli -- execute-deployment --user_prompt "Your test prompt" --deployment_id DEPLOYMENT_ID
```
