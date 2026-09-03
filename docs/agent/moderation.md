# Moderation and guardrails

This guide explains how to configure moderations (guardrails) for agents in this template. Moderations evaluate prompts before the LLM runs and responses after, and can block, report, or replace content based on configured thresholds.

The `datarobot-moderations[all]` package is already included in `pyproject.toml`. Guards are wired into the agent through the `datarobot_moderation` middleware declared in `workflow.yaml` and applied by the [DRAgent front server](./README.md#front-server).

| Section | Description |
|---|---|
| [Overview](#overview) | How moderations fit into the agent request path. |
| [Guard configuration file](#guard-configuration-file) | Shared YAML schema and file placement. |
| [Wire the middleware](#wire-the-middleware) | Hook `datarobot_moderation` into the workflow. |
| [Configure guards](#configure-guards) | Two ways to specify guards (external file or inline). |
| [Test moderations locally](#test-moderations-locally) | Run prompts through the configured guards. |
| [Environment variables](#environment-variables) | Credentials and runtime toggles. |
| [Disable moderations](#disable-moderations) | Turn guards off without removing configuration. |
| [Local evaluation](#local-evaluation) | Offline `nat eval` quality checks during development (separate from runtime guards). |
| [Further reading](#further-reading) | Full guard type reference and official docs. |

## Overview

Moderations run in two stages:

1. Pre-score (prompt)&mdash;guards evaluate user input before the agent calls the LLM. Blocked prompts never reach the model.
2. Post-score (response)&mdash;guards evaluate agent output after generation. Blocked responses are not returned to the caller.

Both stages are implemented by the `datarobot_moderation` middleware on DRAgent, which loads guard definitions from either `moderation_config.yaml` or an inline `moderation` block in `workflow.yaml`.

> **Note:** Runtime moderations (this guide) enforce guardrails on live traffic. For **offline evaluation** during local development&mdash;batch-scoring agent outputs with `nat eval` without deploying&mdash;see [Local evaluation](./evaluation.md).

## Guard configuration file

The guard configuration file defines guard behavior using a shared YAML schema. The following sections cover file placement, an example configuration, LLM judge backends, common guard types, and streaming performance considerations.

### File location

Place `moderation_config.yaml` at the root of the `agent/` directory, alongside `workflow.yaml`:

```text
agent/
├── moderation_config.yaml   # Runtime guard configuration
├── workflow.yaml
└── agent/
    ├── myagent.py
    ├── register.py
    └── ...
```

### Example configuration

LLM-as-a-judge guards route through the DataRobot LLM Gateway via `llm_type: llmGateway` and `llm_gateway_model_id`&mdash;no separate judge deployment is required. Use a judge model that differs from the model the agent uses for more objective scoring.

```yaml
# moderation_config.yaml
timeout_sec: 60
timeout_action: block   # Use "score" to treat timeouts as pass during development.

guards:
  # Pre-score: block toxic prompts before they reach the LLM.
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

Guards that call an LLM to score text (`faithfulness`, `task_adherence`, `agent_goal_accuracy`, and others) require an `llm_type`. Examples in this template use `llmGateway`, which routes through the DataRobot LLM Gateway using `llm_gateway_model_id`&mdash;no judge deployment required. Alternatively, set `llm_type: datarobot` with a 24-character `deployment_id` to use a dedicated DataRobot LLM deployment as the judge.

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

> **Warning:** Guards that call an external model or LLM&mdash;such as `llm_type: llmGateway`, `llm_type: datarobot`, or `type: model`&mdash;can be slow in streaming mode. Post-score guards may run on each streamed chunk rather than only on the final response, so every chunk can trigger a separate judge or model invocation.
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

If no guards are configured, the middleware is a no-op. Add guards using one of the two methods in [Configure guards](#configure-guards).

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

When agent memory (`mem0` or `datarobot_memory_service`) is enabled, the workflow type is `streaming_memory_agent` and the template does not add `datarobot_moderation` to the workflow middleware list. Add it manually to enable runtime guardrails with memory-enabled agents.

## Configure guards

Configure guards using one of two methods:

**Option 1 &mdash; external file (recommended)**

Create `moderation_config.yaml` at the agent directory root. The middleware loads it automatically when no inline configuration is present:

```yaml
middleware:
  datarobot_moderation:
    _type: datarobot_moderation
    # moderation_config.yaml is loaded from the agent directory when present.
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

Blocked responses surface as content-filter events in the streaming path or as the guard intervention message in non-streaming mode.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATAROBOT_ENDPOINT` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot instance URL (for example, `https://app.datarobot.com/api/v2`). Set in `.env` by `dr start`. |
| `DATAROBOT_API_TOKEN` | Yes (for LLM Gateway and DataRobot model guards) | DataRobot API token. Set in `.env` by `dr start`. |
| `DISABLE_MODERATION` | No | Set to `true` to disable all guards at runtime without removing configuration. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | On the Workload API runtime | OTel collector base URL for guard telemetry. Custom Models deployments get one from the platform; workloads do not, so set it in `.env` and the infra forwards it into the container. See [Deployment runtimes](./deployment-runtimes.md#configuration). |

## Disable moderations

To temporarily disable all guards without deleting configuration:

```sh
export DISABLE_MODERATION=true
```

Or add `DISABLE_MODERATION=true` to `.env`. Guards resume when the variable is unset or set to any value other than `true`.

## Local evaluation

Runtime moderations (this guide) enforce guardrails on live agent traffic through the DRAgent middleware.

For **offline evaluation** during local development&mdash;batch-scoring agent responses against the same out-of-the-box metrics without deploying&mdash;use **`nat eval`** with DataRobot moderation evaluators from `datarobot-genai`. That workflow is documented in [Local evaluation for agentic workflows](./evaluation.md).

| Mechanism | Purpose | Used by |
|---|---|---|
| `moderation_config.yaml` | Runtime guardrails on live traffic | `datarobot_moderation` middleware in `workflow.yaml` |
| `eval/*.yaml` + JSON datasets | Offline quality gates | `nat eval` CLI / Pytest |

## Further reading

| Topic | Link |
|---|---|
| Guard types, LLM backends, and full YAML reference | [datarobot-moderations on PyPI](https://pypi.org/project/datarobot-moderations/) |
| Local evaluation with Pytest | [Local evaluation](./evaluation.md) |
| DRAgent front server | [Front server](./README.md#front-server) |
| DRAgent debugging and CLI | [Debugging](./debugging.md) |
| `dr-moderation` CLI (evaluate configs without deploying) | [datarobot-moderations CLI docs](https://pypi.org/project/datarobot-moderations/) |
