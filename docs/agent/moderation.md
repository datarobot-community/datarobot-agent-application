# Moderation and guardrails

This guide explains how to configure **moderations** (guardrails) for agents in this template. Moderations evaluate prompts before the LLM runs and responses after, and can block, report, or replace content based on thresholds you define.

The `datarobot-moderations[all]` package is already included in `pyproject.toml`. Guards are wired into the agent through the `datarobot_moderation` middleware declared in `workflow.yaml` and applied by the [DRAgent front server](./README.md#front-server).

| Section | Description |
|---|---|
| [Overview](#overview) | How moderations fit into the agent request path. |
| [Guard configuration file](#guard-configuration-file) | Shared YAML schema and file placement. |
| [Wire the middleware](#wire-the-middleware) | Hook `datarobot_moderation` into your workflow. |
| [Configure guards](#configure-guards) | Two ways to specify guards (external file or inline). |
| [Test moderations locally](#test-moderations-locally) | Run prompts through your configured guards. |
| [Environment variables](#environment-variables) | Credentials and runtime toggles. |
| [Disabling moderations](#disabling-moderations) | Turn guards off without removing configuration. |
| [Local evaluation](#local-evaluation) | Quality gates in Pytest (separate from runtime guards). |
| [Further reading](#further-reading) | Full guard type reference and official docs. |

## Overview

Moderations run in two stages:

1. **Pre-score (prompt)**&mdash;guards evaluate the user's input before the agent calls the LLM. Blocked prompts never reach the model.
2. **Post-score (response)**&mdash;guards evaluate the agent's output after generation. Blocked responses are not returned to the caller.

Both stages are implemented by the `datarobot_moderation` middleware on DRAgent, which loads guard definitions from either `moderation_config.yaml` or an inline `moderation` block in `workflow.yaml`.

> [!NOTE]
> Runtime moderations (this guide) enforce guardrails on live traffic. For **offline quality gates** in Pytest&mdash;scoring agent outputs in CI without deploying&mdash;see [Local evaluation](./evaluation.md).

## Guard configuration file

### File location

Place `moderation_config.yaml` at the root of the `agent/` directory, alongside `workflow.yaml`:

```
agent/
├── moderation_config.yaml   # Runtime guard configuration
├── workflow.yaml
└── agent/
    ├── myagent.py
    ├── register.py
    └── ...
```

### Example configuration

LLM-as-a-judge guards route through the DataRobot LLM Gateway via `llm_type: llmGateway` and `llm_gateway_model_id`&mdash;no separate judge deployment is required. Use a judge model that is **different from the model your agent uses** for more objective scoring.

```yaml
# moderation_config.yaml
timeout_sec: 60
timeout_action: block   # use "score" to treat timeouts as pass during development

guards:
  # Pre-score: block toxic prompts before they reach the LLM
  - name: Prompt Token Limit
    type: ootb
    ootb_type: token_count
    stage: prompt
    intervention:
      action: block
      message: "Prompt is too long."
      conditions:
        - comparator: greaterThan
          comparand: 4000

  # Post-score: LLM-as-a-judge for agentic workflows
  - name: Agent Goal Accuracy
    type: ootb
    ootb_type: agent_goal_accuracy
    stage: response
    is_agentic: true
    llm_type: llmGateway
    llm_gateway_model_id: "anthropic/claude-opus-4-20250514"
    intervention:
      action: block
      message: "Agent failed to achieve the user's goal."
      conditions:
        - comparator: lessThan
          comparand: 0.7
```

### LLM judge backends

Guards that call an LLM to score text (`faithfulness`, `task_adherence`, `agent_goal_accuracy`, and others) require an `llm_type`. This template's examples use **`llmGateway`**, which routes through the DataRobot LLM Gateway using `llm_gateway_model_id`&mdash;no judge deployment required. Alternatively, set `llm_type: datarobot` with a 24-character `deployment_id` to use a dedicated DataRobot LLM deployment as the judge.

### Common guard types

| Guard (`ootb_type` or `type`) | Stage | Use case |
|---|---|---|
| `token_count` | `prompt` or `response` | Enforce length limits |
| `agent_goal_accuracy` | `response` | Agentic workflows; set `is_agentic: true` and `llm_type: llmGateway` |
| `faithfulness` | `response` | RAG agents; set `copy_citations: true` and `llm_type: llmGateway` |
| `task_adherence` | `response` | Instruction-following agents; set `llm_type: llmGateway` |
| `model` | `prompt` or `response` | Custom DataRobot classifier or text-generation deployment |
| `nemo_guardrails` | `prompt` or `response` | Colang-based NeMo Guardrails flows |

For the complete list of guard types, LLM backends, intervention actions, and comparators, see the [Guardrails Configuration Guide](https://pypi.org/project/datarobot-moderations/) on PyPI.

### Streaming performance

> [!WARNING]
> Guards that call an external model or LLM&mdash;such as `llm_type: llmGateway`, `llm_type: datarobot`, or `type: model`&mdash;can be **slow in streaming mode**. Post-score guards may run on **each streamed chunk** rather than only on the final response, so every chunk can trigger a separate judge or model invocation.
>
> For streaming workloads, prefer lightweight local guards (for example `token_count`) or reserve LLM-as-a-judge and model guards for non-streaming requests. If guards time out during streaming, increase `timeout_sec` or set `timeout_action: score` while tuning thresholds.

## Wire the middleware

Generated `workflow.yaml` files include a `datarobot_moderation` middleware definition. For most frameworks (LangGraph, CrewAI, LlamaIndex, Base), the workflow also lists the middleware in the `workflow.middleware` block:

```yaml
workflow:
  _type: langgraph_agent
  llm_name: datarobot_llm
  description: LangGraph planner/writer agent
  middleware:
    - datarobot_moderation

middleware:
  datarobot_moderation:
    _type: datarobot_moderation
```

If no guards are configured, the middleware is a no-op. Add guards using one of the two methods below.

### NAT framework

The NAT template ships with the `workflow.middleware` entry commented out. Uncomment it to enable moderations:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  # ...
  middleware:
    - datarobot_moderation
```

### Agent memory workflows

When agent memory (`mem0` or `datarobot_memory_service`) is enabled, the workflow type is `streaming_memory_agent` and the template does not add `datarobot_moderation` to the workflow's middleware list. Add it manually if you want runtime guardrails with memory-enabled agents.

## Configure guards

You can configure guards in two ways:

**Option 1 &mdash; external file (recommended)**

Create `moderation_config.yaml` at the agent directory root. The middleware loads it automatically when no inline configuration is present:

```yaml
middleware:
  datarobot_moderation:
    _type: datarobot_moderation
    # moderation_config.yaml is loaded from the agent directory when present
```

**Option 2 &mdash; inline in `workflow.yaml`**

Add a `moderation` field under `middleware.datarobot_moderation` with the same schema as `moderation_config.yaml`:

```yaml
middleware:
  datarobot_moderation:
    _type: datarobot_moderation
    moderation:
      timeout_sec: 60
      timeout_action: block
      guards:
        - name: Agent Goal Accuracy
          type: ootb
          ootb_type: agent_goal_accuracy
          stage: response
          is_agentic: true
          llm_type: llmGateway
          llm_gateway_model_id: "anthropic/claude-opus-4-20250514"
          intervention:
            action: block
            message: "Agent failed to achieve the user's goal."
            conditions:
              - comparator: lessThan
                comparand: 0.7
```

Inline configuration takes precedence over `moderation_config.yaml` when both are present.

## Test moderations locally

Run a one-off query in-process (no server required):

```sh
task agent:cli -- execute --user_prompt "What is generative AI?"
```

Or start the DRAgent dev server and send requests from another terminal:

```sh
dr run agent:dev
```

Blocked responses surface as content-filter events in the streaming path or as the guard's intervention message in non-streaming mode.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATAROBOT_ENDPOINT` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot instance URL (e.g., `https://app.datarobot.com/api/v2`). Set in `.env` by `dr start`. |
| `DATAROBOT_API_TOKEN` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot API token. Set in `.env` by `dr start`. |
| `DISABLE_MODERATION` | No | Set to `true` to disable all guards at runtime without removing configuration. |

## Disabling moderations

To temporarily disable all guards without deleting configuration:

```sh
export DISABLE_MODERATION=true
```

Or add `DISABLE_MODERATION=true` to `.env`. Guards resume when the variable is unset or set to any value other than `true`.

## Local evaluation

Runtime moderations (this guide) enforce guardrails on live agent traffic through the DRAgent middleware.

For **offline evaluation**&mdash;running the same guard metrics in Pytest to gate CI/CD pipelines&mdash;use a separate `moderation.yaml` file and the `ModerationPipeline` API. That workflow is documented in [Local evaluation for agentic workflows](./evaluation.md).

| File | Purpose | Used by |
|---|---|---|
| `moderation_config.yaml` | Runtime guardrails on live traffic | `datarobot_moderation` middleware in `workflow.yaml` |
| `moderation.yaml` | Offline quality gates in tests | Pytest + `ModerationPipeline` |

Both files use the same guard schema. You can maintain one file and symlink or copy it to the other name if you want identical thresholds for runtime and CI.

## Further reading

| Topic | Link |
|---|---|
| Guard types, LLM backends, and full YAML reference | [datarobot-moderations on PyPI](https://pypi.org/project/datarobot-moderations/) |
| Local evaluation with Pytest | [Local evaluation](./evaluation.md) |
| DRAgent front server | [Front server](./README.md#front-server) |
| DRAgent debugging and CLI | [Debugging](./debugging.md) |
| `dr-moderation` CLI (evaluate configs without deploying) | [datarobot-moderations CLI docs](https://pypi.org/project/datarobot-moderations/) |
