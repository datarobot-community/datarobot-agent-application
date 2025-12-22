# DataRobot Agent Development Guide

This guide explains how to develop and deploy custom agents using the DataRobot agent template.

## Template Initialization

**IMPORTANT** Run the following shell commands to initialize the tempalte (in the same directory where AGENTS.md is located):
**IMPORTANT** The following command MUST be run in an interactive terminal session.

```shell
dr start
```

## Overview

Agents in this template are built using **LangGraph** and inherit from the `LangGraphAgent` base class. This provides a standardized structure for creating agents that integrate with DataRobot's deployment infrastructure.

## Dependecies Installation

Should be ran after agent code modification (in the same directory where AGENTS.md is located):

```shell
dr task run agent:install
```

## Agent Structure

Every agent must be implemented in the following location withing agent template directory (relative to the directory of AGENTS.md file) `agent/agentic_workflow`. None of the other files outside of this directory are related.

Every agent must implement the following components:

### 1. Class Definition

```python
from datarobot_genai.langgraph.agent import LangGraphAgent

class MyAgent(LangGraphAgent):
    """Your agent description here."""
```

**Important**: `MyAgent` class should NOT be renamed!

### 2. Required Properties and Methods in Class Definition

#### `llm()` Method

**CRITICAL**: Do NOT modify, delete, or change this method. It MUST be kept exactly as shown below in your agent implementation:

```python
def llm(
    self,
    preferred_model: str | None = None,
    auto_model_override: bool = True,
) -> ChatLiteLLM:
    api_base = self.litellm_api_base(config.llm_deployment_id)
    model = preferred_model
    if preferred_model is None:
        model = config.llm_default_model
    if auto_model_override and not config.use_datarobot_llm_gateway:
        model = config.llm_default_model
    if self.verbose:
        print(f"Using model: {model}")
    return ChatLiteLLM(
        model=model,
        api_base=api_base,
        api_key=self.api_key,
        timeout=self.timeout,
        streaming=True,
        max_retries=3,
    )
```

**Why this is required**: This method handles model configuration, API authentication, and DataRobot LLM Gateway integration. Changing it will break deployment.

#### `workflow` Property
Defines the agent's execution flow using LangGraph's StateGraph.

```python
@property
def workflow(self) -> StateGraph[MessagesState]:
    langgraph_workflow = StateGraph[
        MessagesState, None, MessagesState, MessagesState
    ](MessagesState)

    # Add nodes for each agent component
    langgraph_workflow.add_node("agent_node", self.agent_node)

    # Define edges (workflow connections)
    langgraph_workflow.add_edge(START, "agent_node")
    langgraph_workflow.add_edge("agent_node", END)

    return langgraph_workflow  # type: ignore[return-value]
```

#### `prompt_template` Property
Defines how user input is formatted for the agent.

```python
@property
def prompt_template(self) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("user", "{input}"),
    ])
```

**Important**: The template must accept `{input}` to receive user prompts.

### 3. Agent Nodes

Agent nodes are typically created using `create_react_agent`.

```python
@property
def agent_node(self) -> Any:
    return create_react_agent(
        self.llm(preferred_model="datarobot/azure/gpt-4o-mini"),
        tools=self.tools,  # or [] for no tools
        prompt=make_system_prompt(
            "Your agent's system prompt here."
        ),
    )
```

### 4. Agent tools

**IMPORTANT**: Add required tools in the `agent/agentic_workflow` directory (relative to the directory of AGENTS.md file). Do not add/modify any files outside of this directory. If some of the tools require adding new packages, they should be added to the pyproject.toml and properly installed using command

```shell
dr task run agent:install
```

**IMPORTANT**: Tools must be imported and used in `MyAgent` implementation.


### 5. Preferred LLM model

Preferred model should be set in each ```self.llm(preferred_model="{preffered_model_here}")``` invocation.
**Important**: `preferred_model` parameter must be prefixed with `datarobot/`.


## Agent Testing

Run the following shell commands to run the agent locally (in the same directory where AGENTS.md is located):

```shell
dr task run agent:lint
```

```shell
dr task run agent:test
```

## Agent Validation

Run the following shell commands to run the agent locally (in the same directory where AGENTS.md is located):

```shell
dr task run agent:chainlit
```

## Agent Deployment

Run the following shell commands to deploy the agent (in the same directory where AGENTS.md is located):

```shell
dr task run infra:up-yes
```

In case the deployment fails, you can try deleting it by running the following command:

```shell
dr task run infra:down-yes
```


## Post Deployment Validation

Run the following shell command to validate the agent after deployment (in the same directory where AGENTS.md is located). If the response has no errors then the deployment is successful.

```shell
task agent:cli -- execute-deployment --user_prompt 'Agent specific prompt to validate that it's working' --deployment_id <deployment_id>
```
