# Project Instructions

These instructions apply to all agents working in this repository.

## Running Shell Commands In Project

**IMPORTANT**: All shell commands must be executed from the project root directory.

## Run Project Locally

Run the following shell commands to run the project locally (agent + backend + frontend)

```shell
dr run dev
```

# Agent Development Instructions

## Dependencies Installation

The following command should be run after agent code modification:

```shell
dr task run agent:install
```

> **Warning:** When using a custom Docker context (`DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` is unset and an `agent/docker_context/` folder is present), modifying `pyproject.toml` or `uv.lock` triggers a full execution environment rebuild on the next deployment. This rebuild can take **10–20 minutes** depending on the number of dependencies. When using the default DataRobot execution environment (the default configuration), dependency changes do not trigger a rebuild.

## Agent Structure

Agent must be implemented in the following location withing the `agent/agent` directory. None of the other files outside of this directory are related.

For detailed documentation, see [docs/agent/README.md](../docs/agent/README.md).



Agent must implement the following components:

### 1. Class Definition

`MyAgent` is generated using `datarobot_agent_class_from_langgraph` with a graph factory and prompt template:

```python
from datarobot_genai.langgraph.agent import datarobot_agent_class_from_langgraph

MyAgent = datarobot_agent_class_from_langgraph(graph_factory, prompt_template)
```

**Important**: `MyAgent` class should NOT be renamed!

### 2. Prompt Template

Define a `ChatPromptTemplate` that structures user input:

```python
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Chat history: {chat_history}"),
    ("user", "The topic is {topic}."),
])
```

### 3. Graph Factory

Define a function that receives an LLM, tools, and verbosity flag, and returns a `StateGraph`:

```python
def graph_factory(llm, tools, verbose=False):
    planner = create_agent(llm, tools=tools,
        system_prompt=make_system_prompt("You are a content planner. ..."),
        name="planner_agent", debug=verbose)
    writer = create_agent(llm, tools=tools,
        system_prompt=make_system_prompt("You are a content writer. ..."),
        name="writer_agent", debug=verbose)

    workflow = StateGraph(MessagesState)
    workflow.add_node("planner_node", planner)
    workflow.add_node("writer_node", writer)
    workflow.add_edge(START, "planner_node")
    workflow.add_edge("planner_node", "writer_node")
    workflow.add_edge("writer_node", END)
    return workflow
```

**IMPORTANT**: Use `create_agent` from `langchain.agents` to create agent nodes. Use `make_system_prompt()` from `datarobot_genai.core.agents` for consistent prompt formatting.

### 4. LLM Resolution

The LLM is resolved via `get_llm()` from `datarobot_genai.langgraph.llm` in `custompy_adaptor`:

```python
from datarobot_genai.langgraph.llm import get_llm

agent = MyAgent(
    llm=get_llm(model_name=model_name),
    ...
)
```

**CRITICAL**: Do NOT instantiate LLMs directly. Always use `get_llm()` which handles DataRobot LLM Gateway integration, deployed models, and external LLM providers. To add primary/fallback provider support, use `get_router_llm()` instead — see [LLM provider fallback](../docs/agent/llm-fallback.md).

### 5. Agent tools

**IMPORTANT**: Add required tools in the `agent/agent` directory. Do not add/modify any files outside of this directory. If some of the tools require adding new packages, they should be added to the pyproject.toml and properly installed using command

```shell
dr task run agent:install
```

**IMPORTANT**: Tools must be imported and passed to agent nodes inside `graph_factory`.

For detailed LangGraph documentation, see [docs/agent/frameworks/langgraph.md](../docs/agent/frameworks/langgraph.md).

## Agent Testing

Review and update the tests in the `agent/tests` directory after code changes were made to the agent.
Run the following shell commands to run the tests:

```shell
dr task run agent:lint
```

```shell
dr task run agent:test
```

## Post Deployment Validation

Run the following shell command to validate the agent after deployment. If the response has no errors then the deployment is successful.

```shell
task agent:cli -- execute-deployment --user_prompt "Agent specific prompt to validate that it's working" --deployment_id <deployment_id>
```

## Setting up custom metric and report values

Refer to [Custom metrics](../docs/agent/custom-metrics.md) page for how to set up and report values to custom metrics.

## Migrations

### 11.8.8 — New agent format (class-based → factory-based)

Starting with agent component version 11.8.8 ([af-component-agent#474](https://github.com/datarobot-community/af-component-agent/pull/474)), agent templates (except `base`) no longer require defining agents within a `MyAgent` class. Agents are now defined using native framework primitives at module level and converted to `MyAgent` via a helper function (`datarobot_agent_class_from_*`). The LLM is also decoupled from the agent class and injected via `get_llm()`.

If you are upgrading an existing agent from a version prior to 11.8.8, follow the migration guide for your framework:

- [LangGraph migration](../docs/agent/frameworks/migration-to-11.8.8-langgraph.md)
- [CrewAI migration](../docs/agent/frameworks/migration-to-11.8.8-crewai.md)
- [LlamaIndex migration](../docs/agent/frameworks/migration-to-11.8.8-llamaindex.md)
- [Base agent migration](../docs/agent/frameworks/migration-to-11.8.8-base.md)
- [NAT agent migration](../docs/agent/frameworks/migration-to-11.8.8-nat.md)
# MCP Server Development Instructions

The MCP server MUST be implemented in the `mcp_server/` directory.
By default it provides tools for DataRobot operations, but can be extended with custom tools for any domain.

## MCP Server Development Guidelines

IMPORTANT: Do NOT import code from `agent/` or `fastapi_server/` directories. The MCP server has independent dependencies to avoid conflicts.
IMPORTANT: The MCP server runs as an independent service. Agents connect to it via MCP protocol (HTTP), not direct Python imports.

- You may modify files ONLY inside `mcp_server/` directory.
- The MCP server is a standard FastMCP application:
  * Tools live in `mcp_server/app/tools/`
  * Prompts live in `mcp_server/app/prompts/`
  * Resources live in `mcp_server/app/resources/`
  * Configuration is in `mcp_server/app/core/`
  * Tests are in `mcp_server/app/tests/`
- Read `mcp_server/docs` to further understand the existing structure.

## Tool Development Architecture

The MCP server uses auto-discovery for tools:

1. **Tool Definition** (`mcp_server/app/tools/{domain}_tools.py`): Define tools with `@dr_mcp_tool` decorator
2. **Auto-Discovery**: Server automatically loads all tools from `mcp_server/app/tools/` on startup
3. **MCP Protocol**: Agents discover and call tools via HTTP (no imports needed)

**When adding new tools:**
- Create tool functions in `app/tools/{domain}_tools.py`
- Use `@dr_mcp_tool(tags={"category", "action"})` decorator
- Define parameters with `Annotated[type, "description"]`
- Return `ToolResult(structured_content={...})`
- Tools are automatically discovered - no registration needed

**CRITICAL - Tool Implementation Requirements:**

All tool functions MUST be `async def` and return `ToolResult`. Example:

```python
from typing import Annotated
from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.tools.tool import ToolResult

@dr_mcp_tool(tags={"domain", "action"})
async def tool_name(
    param: Annotated[str, "Parameter description for LLM"],
) -> ToolResult:
    """
    Tool description that the LLM will see.
    Be clear and specific about what the tool does.
    """
    # Your implementation here
    result = {"key": "value"}
    return ToolResult(structured_content=result)
```

## MCP Server Security

- NEVER hardcode API keys or secrets in tool code. Use environment variables or runtime parameters.
- Store credentials in `.env` file (never commit to git)
- Access config via `app/core/user_config.py`
- Use DataRobot credentials management for production deployments

## Installing MCP Server packages

Before making any changes to the mcp_server code, install dependencies by running shell command:

```shell
dr task run mcp_server:install
```

## MCP Server Testing

```shell
dr task run mcp_server:lint
```

```shell
dr task run mcp_server:test
```

# Backend Development Instructions

The agent application template includes a backend implementation in `fastapi_server/`.
By default it ships a backend implementing APIs endpoints for the frontend application.

## Backend Development Guidelines

- The FastAPI backend in `fastapi_server/` already serves the chat API at `/api/v1/`.
  If the user's frontend needs new data endpoints, add them in `fastapi_server/app/api/v1/`.
- The entry point for the backend can be found at `fastapi_server/app/main.py`
- For POST endpoints accepting JSON body, use Pydantic models (not function parameters). Query params go in function signature, body params go in Pydantic model.

## Installing backend packages

Before making any changes to the backen code, install dependencies by running shell command:

```shell
dr task run fastapi_server:install
```

## Backend Testing

```shell
dr task run fastapi_server:lint
```

```shell
dr task run fastapi_server:test
```

# Frontend Development Instructions

The agent application frontend MUST be implemented in the following location withing the `frontend_web/`.
The technology stack is TypeScript + React + Vite + Tailwind CSS + shadcn/ui.
By default it ships a chat UI, but it can reimplemented to contain dashboards, multi-page apps, or other custom UIs.

## Frontend Development Guidelines

IMPORTANT: Do NOT replace this stack with a different framework (e.g. Next.js, Vue, Angular, Svelte). If the user asks to switch frameworks, because deployment pipeline and infrastructure depend on the current stack.
IMPORTANT: The frontend depends on backend API endpoints and agent tool outputs being in place.

- You may modify files ONLY inside `frontend_web/` and `fastapi_server/` for the frontend work.
- The frontend is a standard Vite + React + TypeScript project:
  * Pages live in `frontend_web/src/pages/`
  * Routes are defined in `frontend_web/src/routesConfig.tsx`
  * Reusable components are in `frontend_web/src/components/`
  * UI primitives (shadcn/ui) are in `frontend_web/src/components/ui/`
  * API hooks and requests are in `frontend_web/src/api/`
  * Theming is in `frontend_web/src/theme/`
- Read `frontend_web/README.md` to further understand the existing structure.

### API Architecture

The frontend uses a three-layer architecture for API calls:

1. **API Client** (`src/api/apiClient.ts`): Pre-configured axios instance with base URL
2. **API Requests** (`src/api/{feature}/api-requests.ts`): Functions that make HTTP calls using `apiClient`
3. **React Query Hooks** (`src/api/{feature}/hooks.ts`): Hooks that wrap requests with React Query for caching/state
4. **Pages**: Import and use the hooks

**When adding new API endpoints:**
- Create request functions in `src/api/{feature}/api-requests.ts` using `apiClient` (MUST use default import: `import apiClient from '@/api/apiClient'`)
- Wrap them in React Query hooks in `src/api/{feature}/hooks.ts`
- Import and use the hooks in your pages/components
- Never call `fetch()` or create new axios instances - always use the configured `apiClient`

**CRITICAL - API Path Requirements:**

`apiClient` is already configured with `baseURL` that includes `/api`. Therefore:

Including `/api` in the path will cause **double `/api/api/` URLs** and result in 404/405 errors.

## Frontend  Security
- NEVER embed API keys, secrets, or credentials in frontend code. If the frontend needs to call
  external services, route those calls through `fastapi_server/` endpoints. Do not make direct external API
  calls from browser-side code as this exposes secrets and creates CORS issues.

## Installing frontend packages

Before making any changes to the frontend code, install dependencies (npm packages) by running shell command:

```shell
dr task run frontend_web:install
```

- To install new npm packages, use shell to run `npm install <package>` from the `frontend_web/` directory.

## Installing shadcn/ui components

**CRITICAL**: Before writing ANY code that imports a shadcn/ui component, you MUST first verify the component file exists.

**MANDATORY WORKFLOW:**
1. **BEFORE** writing any import statement for a shadcn/ui component (e.g. `Select`, `Tabs`, `Table`, `Popover`, `DatePicker`, `Dialog`, `Accordion`, etc.)
2. Check if the file exists: `frontend_web/src/components/ui/{component}.tsx`
3. If the file does NOT exist, you MUST run: `npx --yes shadcn@latest add {component} --overwrite` from the `frontend_web/` directory
4. Wait for the installation to complete
5. ONLY THEN write code that imports the component

## Frontend Testing

```shell
dr task run frontend_web:lint
```

```shell
dr task run frontend_web:test
```

## Project Deployment

Run the following shell commands to deploy the project:

```shell
dr task run infra:up-yes
```

In case the deployment process fails, you can try deleting it by running the following command:

```shell
dr task run infra:down-yes
```
