# Moderation and guardrails

This guide explains how to configure **moderations** (guardrails) for agents in this template. Moderations evaluate prompts before the LLM runs and responses after, and can block, report, or replace content based on thresholds you define.

The `datarobot-moderations[all]` package is already included in `pyproject.toml`. Guards share a single YAML schema; how you wire that schema depends on which **front server** serves the agent.

| Section | Description |
|---|---|
| [Overview](#overview) | How moderations fit into the agent request path. |
| [Guard configuration file](#guard-configuration-file) | Shared YAML schema and file placement. |
| [DRUM](#drum) | Runtime guardrails with the default DRUM front server. |
| [DRAgent](#dragent) | Runtime guardrails with the DRAgent front server. |
| [Environment variables](#environment-variables) | Credentials and runtime toggles. |
| [Disabling moderations](#disabling-moderations) | Turn guards off without removing configuration. |
| [Local evaluation](#local-evaluation) | Quality gates in Pytest (separate from runtime guards). |
| [Further reading](#further-reading) | Full guard type reference and official docs. |

## Overview

Moderations run in two stages:

1. **Pre-score (prompt)**&mdash;guards evaluate the user's input before the agent calls the LLM. Blocked prompts never reach the model.
2. **Post-score (response)**&mdash;guards evaluate the agent's output after generation. Blocked responses are not returned to the caller.

This template supports two front servers. Both use the same guard YAML, but the integration point differs:

| Front server | Integration | Config file | When active |
|---|---|---|---|
| **DRUM** | DRUM wraps the `chat()` hook in `custom.py` automatically | `moderation_config.yaml` | Default (`ENABLE_DRAGENT_SERVER` unset or `false`) |
| **DRAgent** | `datarobot_moderation` middleware in `workflow.yaml` | Inline `moderation` field or `moderation_config.yaml` | `ENABLE_DRAGENT_SERVER=true` |

> [!NOTE]
> Runtime moderations (this guide) enforce guardrails on live traffic. For **offline quality gates** in Pytest&mdash;scoring agent outputs in CI without deploying&mdash;see [Local evaluation](./evaluation.md).

## Guard configuration file

### File location

Place `moderation_config.yaml` at the root of the `agent/` directory, alongside `custom.py`, `dev.py`, and `workflow.yaml`:

```
agent/
├── moderation_config.yaml   # Runtime guard configuration (DRUM and DRAgent)
├── custom.py
├── dev.py
├── workflow.yaml
└── agent/
    ├── myagent.py
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
> Guards that call an external model or LLM&mdash;such as `llm_type: llmGateway`, `llm_type: datarobot`, or `type: model`&mdash;can be **slow in streaming mode**. Post-score guards may run on **each streamed chunk** rather than only on the final response, so every chunk can trigger a separate judge or model invocation. This applies to both DRUM and DRAgent streaming paths.
>
> For streaming workloads, prefer lightweight local guards (for example `token_count`) or reserve LLM-as-a-judge and model guards for non-streaming requests. If guards time out during streaming, increase `timeout_sec` or set `timeout_action: score` while tuning thresholds.

## DRUM

**DRUM** (DataRobot User Model) is the default front server. When `moderation_config.yaml` is present in the agent directory, DRUM applies guards automatically around the `chat()` hook in `custom.py`. No changes to `custom.py` or `myagent.py` are required.

### How it works

1. A request arrives at the DRUM prediction server.
2. Pre-score guards evaluate the prompt.
3. If the prompt passes, DRUM calls `chat()` and the agent generates a response.
4. Post-score guards evaluate the response.
5. If a guard's intervention condition fires, the blocked message is returned instead of the agent output.

The local development server (`dev.py`) sets `TARGET_NAME=response` and passes the agent directory as the model path so DRUM can locate `moderation_config.yaml` regardless of the working directory.

### Local development

Start the agent with DRUM (default):

```sh
dr run agent:dev
```

Or run the full application:

```sh
dr run dev
```

Send a test request:

```sh
task agent:cli -- execute --user_prompt '{"topic":"Generative AI"}'
```

If a guard blocks the request, the response contains the guard's `intervention.message` instead of the agent's normal output.

### Deployed environments

When deployed as a DataRobot custom model, DRUM loads `moderation_config.yaml` from the model artifact. Redeploy after changing guard configuration so the new file is included in the deployment package.

`DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` must be available in the deployment environment for guards that call the DataRobot LLM Gateway or model deployments.

## DRAgent

**DRAgent** is the next-generation front server built on NAT (NeMo Agent Toolkit). Moderations are applied through the `datarobot_moderation` middleware declared in `workflow.yaml`.

> [!IMPORTANT]
> DRAgent is experimental. Enable it by setting `ENABLE_DRAGENT_SERVER=true` in your `.env` file. When DRAgent is enabled, the agent CLI is unavailable; use `task agent:cli` or `nat dragent` commands instead. See [Front servers](./README.md#front-servers) for details.

### Enable DRAgent

Add to `.env`:

```sh
ENABLE_DRAGENT_SERVER=true
```

Start the development server:

```sh
dr run agent:dev
```

This runs `nat dragent serve --config_file workflow.yaml` instead of the DRUM-based `dev.py` server.

### Wire the middleware

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

#### NAT framework

The NAT template ships with the `workflow.middleware` entry commented out. Uncomment it to enable moderations when running with DRAgent:

```yaml
workflow:
  _type: per_user_tool_calling_agent
  # ...
  middleware:
    - datarobot_moderation
```

#### Agent memory workflows

When agent memory (`mem0` or `datarobot_memory_service`) is enabled, the workflow type is `streaming_memory_agent` and the template does not add `datarobot_moderation` to the workflow's middleware list. Add it manually if you want runtime guardrails with memory-enabled agents.

### Configure guards

You can configure guards in two ways:

**Option 1 &mdash; external file (recommended)**

Create `moderation_config.yaml` at the agent directory root (same location as for DRUM). The middleware loads it automatically when no inline configuration is present:

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

### Test with DRAgent

Run a one-off query without starting the dev server:

```sh
task agent:cli -- execute --user_prompt "What is generative AI?"
```

Or query a running DRAgent server:

```sh
task agent:cli START_DEV=1 -- execute --user_prompt "What is generative AI?"
```

Blocked responses surface as content-filter events in the streaming path or as the guard's intervention message in non-streaming mode.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATAROBOT_ENDPOINT` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot instance URL (e.g., `https://app.datarobot.com/api/v2`). Set in `.env` by `dr start`. |
| `DATAROBOT_API_TOKEN` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot API token. Set in `.env` by `dr start`. |
| `TARGET_NAME` | DRUM local dev / standalone Python | Response field name for post-score guards. DRUM sets this to `response` in `dev.py`. In deployed DRUM environments, the deployment `target_name` takes precedence. |
| `DISABLE_MODERATION` | No | Set to `true` to disable all guards at runtime without removing configuration. |
| `ENABLE_DRAGENT_SERVER` | DRAgent only | Set to `true` to use the DRAgent front server instead of DRUM. |

## Disabling moderations

To temporarily disable all guards without deleting configuration:

```sh
export DISABLE_MODERATION=true
```

Or add `DISABLE_MODERATION=true` to `.env`. Guards resume when the variable is unset or set to any value other than `true`.

## Local evaluation

Runtime moderations (this guide) enforce guardrails on live agent traffic through DRUM or DRAgent.

For **offline evaluation**&mdash;running the same guard metrics in Pytest to gate CI/CD pipelines&mdash;use a separate `moderation.yaml` file and the `ModerationPipeline` API. That workflow is documented in [Local evaluation for agentic workflows](./evaluation.md).

| File | Purpose | Used by |
|---|---|---|
| `moderation_config.yaml` | Runtime guardrails on live traffic | DRUM, DRAgent middleware |
| `moderation.yaml` | Offline quality gates in tests | Pytest + `ModerationPipeline` |

Both files use the same guard schema. You can maintain one file and symlink or copy it to the other name if you want identical thresholds for runtime and CI.

## Further reading

| Topic | Link |
|---|---|
| Guard types, LLM backends, and full YAML reference | [datarobot-moderations on PyPI](https://pypi.org/project/datarobot-moderations/) |
| Local evaluation with Pytest | [Local evaluation](./evaluation.md) |
| DRUM vs DRAgent front servers | [Front servers](./README.md#front-servers) |
| DRAgent debugging and CLI | [Debugging](./debugging.md) |
| `dr-moderation` CLI (evaluate configs without deploying) | [datarobot-moderations CLI docs](https://pypi.org/project/datarobot-moderations/) |
