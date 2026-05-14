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

    def planner_to_writer_relay(state: MessagesState) -> MessagesState:
        last = state["messages"][-1]
        if isinstance(last, AIMessage):
            return {"messages": [HumanMessage(content=last.content)]}
        return {"messages": []}

    workflow = StateGraph(MessagesState)
    workflow.add_node("planner_node", planner)
    workflow.add_node("planner_to_writer_relay", planner_to_writer_relay)
    workflow.add_node("writer_node", writer)
    workflow.add_edge(START, "planner_node")
    workflow.add_edge("planner_node", "planner_to_writer_relay")
    workflow.add_edge("planner_to_writer_relay", "writer_node")
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
