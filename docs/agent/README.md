# Agent

The agent component is the core of the application. It defines the AI workflow that processes user requests, invokes tools, and produces responses. Agents integrate with DataRobot for LLM access, tool management, and deployment, and can be built using multiple agentic frameworks.

For the official DataRobot documentation on agent components, see [Agent components](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-overview.html).

| Section | Description |
|---|---|
| [Features](#features) | Key capabilities of the agent component. |
| [Agent file structure](#agent-file-structure) | Important files and their organization. |
| [Agent class implementation](#agent-class-implementation-myagentpy) | Agent class and its framework-specific implementation. |
| [Tool integration](#tool-integration) | How agents use tools via MCP, workflow tools, and custom local tools. |
| [Configuration](#configuration) | Agent configuration management. |
| [Front server](#front-server) | DRAgent — the only supported front server |
| [Agent types](#agent-types) | Supported agent frameworks and links to examples. |
| [Debugging](./debugging.md) | Debug agents locally using the CLI, VS Code, and PyCharm. |
| [Tracing and telemetry](./tracing.md) | OpenTelemetry tracing for DRAgent agents: how `register.py` and `workflow.yaml` are instrumented to export spans to DataRobot. |
| [Moderation and guardrails](./moderation.md) | Configure runtime guardrails with `datarobot_moderation` middleware in `workflow.yaml`. |
| [Agent memory](./agent-memory.md) | Persistent per-user memory via `use_agent_memory`: `streaming_memory_agent`, `dr_mem0_memory`, and provider configuration. |
| [Local evaluation](./evaluation.md) | Evaluate agentic workflows locally with Pytest and integrate tests into CI/CD pipelines. |
| [Further reading](#further-reading) | Links to official DataRobot docs for troubleshooting, tracing, global tools, and more. |

## Features

### AG-UI (Agent-User Interaction Protocol)

All agents use [AG-UI](https://docs.ag-ui.com/introduction) as the primary streaming interface. AG-UI is an open, event-based protocol that defines a standard set of event types — lifecycle, text messages, tool calls, state management, and reasoning — that agents emit during execution. This enables the frontend to render real-time progress, tool invocations, and final output consistently across all frameworks.

See the [AG-UI integration guide](./ag-ui.md) for details on each event type and how they are used in this template.

### Agent-to-Agent (A2A)

Agents can expose themselves as A2A servers and connect to remote agents via the agent-to-agent protocol. See [Agent2Agent](./agent2agent.md) for configuration and usage, and [A2A Authentication](./agent2agent-auth.md) for DataRobot API key and Okta XAA auth setup.

## Agent file structure

The agent is implemented in the `agent/` directory. The inner `agent/agent/` package contains the Python code you edit; `workflow.yaml` and other outer files provide NAT orchestration and infrastructure for running and deploying the agent.

```
agent/
├── agent/                  # Agent Python package (your code goes here)
│   ├── __init__.py         # Package exports: MyAgent, Config, custompy_adaptor
│   ├── myagent.py          # Agent definition (framework-specific)
│   ├── config.py           # Configuration management
│   └── register.py         # DRAgent/NAT registration (framework-specific)
├── workflow.yaml           # DRAgent/NAT orchestration config (framework-specific; see note below)
├── tests/                  # Agent tests
│   ├── conftest.py
│   ├── test_agent.py
│   └── ...
├── cli.py                  # CLI for local testing and deployment validation
├── pyproject.toml          # Python dependencies and project metadata
├── Taskfile.yml            # Task runner definitions (install, lint, test)
└── uv.lock                 # Dependency lockfile
```

> [!IMPORTANT]
> **`workflow.yaml` lives at `agent/workflow.yaml`**, not under `agent/agent/`. It is the top-level NAT configuration that DRAgent loads to build the front server, tools, LLMs, and workflow graph. Upgrading from layouts that kept the file at `agent/agent/workflow.yaml`? See [`workflow.yaml` path migration](./migration-workflow-yaml-path.md).

| File | Description |
|---|---|
| `agent/agent/myagent.py` | **Framework-specific.** Contains the main agent implementation. Defines the `MyAgent` class. The implementation varies by framework — see [Agent types](#agent-types) for details. |
| `agent/agent/config.py` | Manages configuration loading from environment variables, runtime parameters, and DataRobot credentials. |
| `agent/agent/register.py` | **Framework-specific.** NAT registration module used by DRAgent. Wires LLM, MCP tools, workflow tools, and the agent together. |
| `agent/workflow.yaml` | **Framework-specific.** Declarative NAT workflow configuration: front-end type, A2A metadata, LLM component, workflow type, middleware, and memory wrappers. Loaded by DRAgent for every framework. |

**Note:** The files `myagent.py`, `register.py`, and `workflow.yaml` are generated from framework-specific templates during project setup. Their content depends on the chosen agent framework (LangGraph, CrewAI, LlamaIndex, NAT, or Base).

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

MCP and tool wiring happen in `register.py`&mdash;see the framework-specific docs for that path.

**Important:** The name `MyAgent` must not be changed&mdash;it is referenced by the framework infrastructure.

### Tools

`MyAgent` accepts a `tools` parameter at initialization. The agent class does **not** load MCP tools inside `invoke()`&mdash;callers obtain tools externally in `register.py` and supply them to the agent:

| Mechanism | When to use |
|---|---|
| `tools=` constructor argument | Pass the merged tool list when constructing `MyAgent` in `register.py`. |
| `set_tools()` | Update tools after initialization; propagates to sub-agents in multi-agent frameworks such as CrewAI and LlamaIndex. |

To access MCP, call `mcp_tools_context()` **outside** the agent class&mdash;in `register.py`, use `async with mcp_tools_context(mcp_config) as mcp_tools`, merge with workflow tools, and pass the result to `MyAgent(..., tools=tools)`.

See the framework-specific docs for complete examples.

See the framework-specific documentation for detailed implementation guides:

- [Base](./frameworks/base.md)&mdash;manual `invoke()` with AG-UI events.
- [LangGraph](./frameworks/langgraph.md)&mdash;`StateGraph` with `create_agent` nodes.
- [CrewAI](./frameworks/crewai.md)&mdash;agents, tasks, and crews.
- [LlamaIndex](./frameworks/llamaindex.md)&mdash;`FunctionAgent` and `AgentWorkflow`.
- [NAT](./frameworks/nat.md)&mdash;fully declarative YAML configuration.

## Tool integration

Agents can use tools to extend their capabilities. Tools are supplied to `MyAgent` at initialization (via the `tools` parameter) or updated afterward with `set_tools()`. The agent class does not fetch MCP tools internally&mdash;callers load MCP explicitly in `register.py` and pass the resulting tool list in.

Agents can combine tools from multiple sources. LangGraph, CrewAI, and LlamaIndex often use in-repo tool functions passed into the graph, crew, or workflow; **NAT** custom tools are registered with `nat_tool` in `register.py`, declared under `functions` in `workflow.yaml`, and rely on importing `agent.register` at startup&mdash;see [NAT custom local tools](./frameworks/nat.md#custom-local-tools).

### MCP tools

MCP tools are loaded in `register.py` by calling `mcp_tools_context()` from the framework-specific adapter in `datarobot_genai` (e.g. `datarobot_genai.langgraph.mcp`, `datarobot_genai.crewai.mcp`). This call happens **outside** `MyAgent`, not inside `invoke()`. See [MCP server](../mcp-server.md) for MCP server configuration.

```python
async with mcp_tools_context(mcp_config) as mcp_tools:
    agent = MyAgent(..., tools=workflow_tools + mcp_tools)
```

### Workflow tools

Tools listed in `workflow.yaml` under `tool_names` are resolved by the NeMo (NAT) builder at startup (workflow tools, MCP function groups, A2A clients, and NAT `functions`). Under **NAT as the agent framework** (`per_user_tool_calling_agent`), this YAML wiring is the primary way tools are exposed; LangGraph and other frameworks use `workflow.yaml` for workflow tools and MCP in addition to framework-native tools. See [Agent2Agent](./agent2agent.md).

### Custom local tools

**If you chose the [NAT](./frameworks/nat.md) framework:** read [NAT `workflow.yaml` requirements](./frameworks/nat.md#nat-workflowyaml-requirements-read-this-first) first. Do **not** use `_type: python_function` in `functions` for custom Python tools. Use `nat_tool` in `register.py`, a matching `functions.<name>` block with `_type` equal to that name, and include the name in `workflow.tool_names`. Every `nat_tool` name must appear in YAML or you will see `Function '…' not found in list of functions`. Follow the [checklist](./frameworks/nat.md#checklist-every-custom-nat_tool-must-appear-in-functions-do-not-skip).

For **LangGraph** (and similar code-first frameworks), add tool functions under `agent/agent/` and pass them into your graph or agents, for example:

```python
from langchain_core.tools import tool

@tool
def my_custom_tool(query: str) -> str:
    """Description of what the tool does."""
    return "result"
```

### Authorization context

DRAgent automatically resolves the authorization context for tools that require access tokens, so tools can securely call external services using DataRobot's credential management. No agent-side code is required.

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

For LLM configuration details, see [LLM component](../llm.md). To configure primary and fallback LLM providers, see [LLM provider fallback](./llm-fallback.md). To enable persistent per-user memory across conversations, see [Agent memory](./agent-memory.md).

## Front server

The agent component runs on the **DRAgent** front server&mdash;a NAT (NeMo Agent Toolkit) + FastAPI runtime that loads `workflow.yaml`, builds the workflow graph, and serves the agent over HTTP. DRAgent is wired in for every framework (LangGraph, CrewAI, LlamaIndex, NAT, Base).

- **Entry point**&mdash;`register.py` + `workflow.yaml`, using NAT's declarative workflow registration.
- **Execution model**&mdash;fully asynchronous (native `async`/`await`).
- **Streaming**&mdash;native async streaming via `DRAgentEventResponse`.
- **Local dev**&mdash;the Taskfile runs `nat dragent serve --config_file workflow.yaml` on port `AGENT_PORT` (default `8842`). CLI commands (`task agent:cli -- execute …`) are forwarded to `nat dragent run`/`query` and run the workflow in-process without a server.
- **Deployment**&mdash;the `ENABLE_DRAGENT_SERVER` runtime parameter on the custom model is set automatically by the infrastructure (see `template/infra/infra/<agent_app_name>.py`).

DRAgent is required for [Agent-to-Agent (A2A)](./agent2agent.md), [agent memory](./agent-memory.md), and `workflow.yaml`-driven [moderation middleware](./moderation.md).

### DRUM fallback (deprecated, temporary)

The legacy DRUM front server (`custom.py` + `dev.py`) is **deprecated and scheduled for removal**. It remains in the template only as a temporary escape hatch in case you hit a blocker with DRAgent.

To disable DRAgent and fall back to DRUM, set in your `.env` file:

```sh
ENABLE_DRAGENT_SERVER=false
```

Then restart the dev server (`dr run agent:dev` / `dr run dev`). In deployed environments, override the `ENABLE_DRAGENT_SERVER` runtime parameter on the custom model to `false`.

> [!WARNING]
> When DRUM is active, [A2A](./agent2agent.md), [agent memory](./agent-memory.md), and the [`datarobot_moderation` middleware](./moderation.md) are unavailable. Do not rely on `ENABLE_DRAGENT_SERVER=false` for production workloads; report any DRAgent issues so the underlying bug can be fixed before DRUM is removed.

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

### 11.9.3 — `workflow.yaml` location

Agent component 11.9.3 moved `workflow.yaml` from `agent/agent/workflow.yaml` to `agent/workflow.yaml`. DRAgent loads this file at startup. See [`workflow.yaml` path migration](./migration-workflow-yaml-path.md).

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
| All frameworks | [`workflow.yaml` path (11.9.3)](./migration-workflow-yaml-path.md) |

## Further reading

The following topics are covered in the official DataRobot documentation:

| Topic | Description |
|---|---|
| [Troubleshooting](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-troubleshooting.html) | Diagnose and resolve common issues with agent setup, deployment, LLM gateway, and imports. |
| [Tracing and telemetry](./tracing.md) | How DRAgent agents are instrumented for OpenTelemetry tracing and export spans to DataRobot. |
| [Implement tracing](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html) | Add custom OpenTelemetry tracing to agent tools for monitoring and debugging deployed agents. |
| [Deploy agentic tools](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tools.html) | Deploy global tools from the DataRobot Registry (search datasets, make predictions, render charts). |
| [DataRobot agentic skills](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-skills.html) | Install modular skill packages for coding agents (Cursor, Claude Code, Codex, and others). |
| [A2A authentication](./agent2agent-auth.md) | DataRobot API key and Okta cross-application access (XAA) for agent-to-agent authentication. |
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

Run the workflow in-process via DRAgent (no running server required):

```sh
task agent:cli -- execute --user_prompt '{"topic":"Generative AI"}'
```

### Validate a deployment

```sh
task agent:cli -- execute-deployment --user_prompt "Your test prompt" --deployment_id DEPLOYMENT_ID
```
