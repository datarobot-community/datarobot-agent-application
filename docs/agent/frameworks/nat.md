# NAT agent

The NAT (NVIDIA NeMo Agent Toolkit) agent uses a YAML-first configuration to define agents, tools, and workflows. Orchestration and built-in function types are declared in `workflow.yaml`; [custom local tools](#custom-local-tools) also use short Python in `register.py` (`nat_tool`) as described below.

## NAT `workflow.yaml` requirements (read this first)

**NAT validates `workflow.yaml` with a fixed schema.** Other parts of this repository document LangGraph-oriented patterns; those are **not** valid inside NAT’s `functions` block unless a NAT discriminator explicitly supports them.

1. **Do not use `python_function` in `functions`.** Some examples in the ecosystem use `_type: python_function` with `module_path` and `function_name` to point at Python callables. That is **not** a valid [NAT function discriminator](https://docs.nvidia.com/nemo/agent-toolkit/index.html). You will get errors such as: `Input tag 'python_function' found using discriminator() does not match any of the expected tags`. For custom code, use **`nat_tool` in `register.py` plus a matching `functions` entry** (see [Custom local tools](#custom-local-tools) below) or only [built-in NAT `/_type` values](https://docs.nvidia.com/nemo/agent-toolkit/index.html).

2. **Every name in `workflow.tool_names` must exist** as a key under `functions:` and/or `function_groups:`. If you add `nat_tool(my_fn, "my_tool", ...)` in `register.py` but omit `functions.my_tool` in `workflow.yaml`, you will get: `ValueError: Function 'my_tool' not found in list of functions`. Python registration alone does not create the YAML entry the NeMo builder loads.

3. **A2A and `functions` are different.** The `general.front_end.a2a` block (skills, server name, examples) is for Agent2Agent discovery and must be valid YAML, but it **does not** define callable tools. Tools are still declared under `functions` / `function_groups` and listed in `workflow.tool_names` as in this document. For `skills` / `examples`, **avoid unquoted flow sequences** like `[a?, b: c]`&mdash;characters such as `?` or `:` after a word can confuse the YAML parser; use a block list (lines starting with `-`) or **double-quoted** strings in flow style.

4. **Prefer `typing.Annotated` on parameters** for custom `nat_tool` functions so the LLM sees clear argument descriptions (see [Custom local tools](#custom-local-tools)).

5. **`register.py` must be imported at startup** when it contains `nat_tool(...)` calls. The `nat_tool` helper registers your tool with NeMo’s workflow registry when the module **loads**. Generated NAT projects ship a stub `register.py` and `import agent.register  # noqa: F401` in `myagent.py` so adding `nat_tool` later does not require wiring a new import. If you remove that import, add it back (or import `register` at the top of `agent/__init__.py` *before* `from agent.myagent import ...`) before relying on custom tools; otherwise the runtime can fail when resolving tool implementations.

## Checklist: every custom nat_tool must appear in functions (do not skip)

**NeMo builds the callable list from the `functions` (and `function_groups`) section of `workflow.yaml`.** `nat_tool` in Python does not remove the need for YAML. For **each** name you pass as the second argument to `nat_tool`, you **must** add a matching `functions` entry, or you will get `ValueError: Function '…' not found in list of functions`.

Use this table whenever you add, rename, or remove a custom tool:

| # | You change… | You must also… |
|---|----------------|-----------------|
| 1 | Add `nat_tool(my_fn, "my_tool", …)` in `register.py` | Add `functions.my_tool` with `_type: my_tool` and a `description`, and add `my_tool` to `workflow.tool_names` |
| 2 | Add a name to `workflow.tool_names` | It must be a `functions` key, a `function_groups` key (e.g. `mcp_tools`), or it will fail at runtime |
| 3 | Remove a tool | Remove it from `nat_tool` calls, `functions`, and `workflow.tool_names` together |

**Quick self-check (before `dr run` / `task agent:cli`):** For `per_user_tool_calling_agent`, take every name listed under `workflow.tool_names`. For each name, confirm either `functions.<name>` exists **or** `function_groups.<name>` exists. Anything else is an error.

Details and examples: [Custom local tools](#custom-local-tools).

## `myagent.py`

Unlike the other frameworks, NAT agents are defined entirely in `workflow.yaml`. The `myagent.py` file contains a minimal `MyAgent` class that loads the YAML. The template also imports `agent.register` so `nat_tool(...)` side effects run when you add them in `register.py`:

```python
from pathlib import Path

from datarobot_genai.nat.agent import NatAgent

import agent.register  # noqa: F401 - load nat_tool(fn, name, ...) registrations from register.py

class MyAgent(NatAgent):
    def __init__(self, *args, workflow_path=Path(__file__).parent / "workflow.yaml", **kwargs):
        super().__init__(*args, workflow_path=workflow_path, **kwargs)
```

The `workflow.yaml` defines everything:

**Functions** (sub-agents)&mdash;defined as `chat_completion` types with system prompts:

```yaml
functions:
  planner:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content planner...
  writer:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content writer...
```

**Workflow**&mdash;a `per_user_tool_calling_agent` that orchestrates which functions to call:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
  system_prompt: |
    You are a blog content orchestrator. For every user request:
    1. Call planner to get a content plan.
    2. Call writer with the content plan as input.
    Return only the final blog post.
```

**LLMs**&mdash;configured directly in YAML rather than in Python:

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-component
```

You can define multiple LLMs and assign them to different functions.

## Tool integration

NAT manages tools primarily in `workflow.yaml`. Built-in function types and MCP/A2A clients are declared there; custom Python tools also need `nat_tool` registration (see [Custom local tools](#custom-local-tools)).

### MCP tools

MCP tools are configured as a `function_group` and referenced in `tool_names` in the workflow:

```yaml
function_groups:
  mcp_tools:
    _type: datarobot_mcp_client

workflow:
  _type: per_user_tool_calling_agent
  tool_names:
    - mcp_tools
```

The MCP tools context in `myagent.py` is a no-op because NAT manages tools entirely in YAML.

### A2A remote agent tools

Remote agents are also configured as function groups:

```yaml
function_groups:
  remote_agent:
    _type: authenticated_a2a_client
    url: "https://app.datarobot.com/api/v2/deployments/DEPLOYMENT_ID/directAccess/a2a/"
    auth_provider: datarobot_auth
```

### Custom local tools

To add a custom tool to a NAT agent, define a plain Python function and register it with **`nat_tool(fn, tool_name, ...)`** from `datarobot_genai.nat.tool` in `register.py` (a **call** at module level after the function exists). Then reference `tool_name` in `workflow.yaml`.

**Do not** use `@nat_tool()` as a decorator with no arguments; `nat_tool` requires the function and name as positional arguments, and bare `@nat_tool()` raises `TypeError: nat_tool() missing 2 required positional arguments: 'fn' and 'name'`.

**Step 1**&mdash;Define the tool function (e.g. in `agent/agent/tools.py`):

```python
from typing import Annotated

def generate_objectid(
    type: Annotated[str, "The type of object to generate an ID for. Should be only 'deployment'."],
) -> str:
    """Generate a unique object ID for a deployment."""
    if type != "deployment":
        raise ValueError("Invalid type")
    return "69cbb73789723b6936c6c9e1"
```

Use `Annotated` type hints to provide parameter descriptions&mdash;NAT uses these to generate the tool schema for the LLM.

**Step 2**&mdash;Register the tool in `register.py`:

```python
from datarobot_genai.nat.tool import nat_tool
from agent.tools import generate_objectid

nat_tool(generate_objectid, "generate_objectid")
```

The second argument is the name of the tool as it will appear in `workflow.yaml`.

**Step 2b**&mdash;Ensure `register.py` is loaded (see [`myagent.py`](#myagentpy)): generated NAT projects already include `import agent.register  # noqa: F401`. If you removed it, add it back before relying on `nat_tool` registrations; otherwise the package may never import `register.py`, and tool implementations will not be registered with NeMo.

**Step 3**&mdash;Add the tool to `workflow.yaml` (required: a `functions` entry for **each** custom tool name, not only `tool_names` on the workflow):

```yaml
functions:
  generate_objectid:
    _type: generate_objectid
    description: A tool that generates an object ID for a deployment.

workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
    - generate_objectid
```

The `_type` in the `functions` section must match the name passed to `nat_tool()`. The tool then becomes available alongside other functions and MCP tools.

You can also define sub-agents as tools using `_type: chat_completion` with a `system_prompt`&mdash;these are built-in function types in NAT that act as callable tools for the orchestrator agent.

For more on NAT tool types, see the [NVIDIA NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/index.html).

## Prompt modification

NAT agents define all prompts declaratively in `workflow.yaml`. You configure two levels: **function system prompts** (sub-agent behavior) and the **workflow system prompt** (orchestrator behavior).

### Function system prompts

Each function in the `functions` section has a `system_prompt` field that defines the behavior of that sub-agent:

```yaml
functions:
  planner:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content planner. You are working with a content writer colleague.
      You're working on planning a blog article about the topic.
      You collect information that helps the audience learn something and make
      informed decisions. Your work is the basis for the Content Writer.
      1. Prioritize the latest trends, key players, and noteworthy news on the topic.
      2. Identify the target audience, considering their interests and pain points.
      3. Develop a detailed content outline including an introduction, key points,
         and a call to action.
      4. Include SEO keywords and relevant data or sources.
    description: A tool that plans the content for the requested topic.
```

- `system_prompt`&mdash;the full system prompt for this function. Use YAML multiline syntax (`|`) for readability.
- `description`&mdash;a short description visible to the orchestrator agent when deciding which tool to call.
- `llm_name`&mdash;which LLM this function uses (references the `llms` section). Different functions can use different LLMs.

### Workflow system prompt

The `workflow` section has its own `system_prompt` that controls the orchestrator&mdash;the top-level agent that decides which functions to call:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
  system_prompt: |
    You are a blog content orchestrator. For every user request, follow these steps:
    1. Call planner to get a content plan.
    2. Call writer with the content plan as input to produce the final blog post.
    Feel free to call the MCP tools as needed.
    Return only the final blog post output from the writer.
  verbose: true
```

This prompt should clearly describe the execution order and what each tool/function does. The orchestrator uses this to decide the sequence of calls.

### How to modify

- **Update function prompts**&mdash;edit the `system_prompt` field in any `functions` entry.
- **Change the orchestration logic**&mdash;modify the `workflow.system_prompt` to change how the orchestrator sequences function calls.
- **Assign different LLMs**&mdash;set `llm_name` per function to use different models for different tasks (e.g. a fast model for planning, a capable model for writing).
- **Add new functions**&mdash;create a new entry in `functions` with `_type: chat_completion`, a `system_prompt`, and a `description`. Then add it to `workflow.tool_names`.
- **Change function descriptions**&mdash;update `description` to influence when the orchestrator calls a function.

### Tips

- The `workflow.system_prompt` is the most impactful prompt&mdash;it controls the overall agent behavior and execution flow.
- Use numbered steps in the workflow prompt to enforce a specific execution order.
- Use `description` on functions to help the orchestrator understand when to call each function.
- Different functions can use different LLMs&mdash;use a faster model for simple tasks and a more capable model for complex ones.
- Test prompt changes by editing `workflow.yaml` and running `task agent:cli -- execute --user_prompt "..."`. No code changes needed.

For more on NAT prompt configuration, see the [NVIDIA NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/index.html).

## When to use

- You want to define agents without writing Python orchestration code.
- You need to iterate quickly on agent prompts and tool configurations via YAML.
- You want to use NAT-native features like built-in tool types, authentication providers, and multi-LLM configurations.

## Streaming

All streaming levels (chunk, step, event) require custom implementation.
