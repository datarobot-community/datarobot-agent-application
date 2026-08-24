# LLM provider fallback

> **Also known as**: failover, model fallback, provider fallback, model routing, graceful degradation, backup provider, secondary model, circuit breaker


The agent component supports configuring primary and fallback LLM providers so that if the primary provider is unavailable or returns an error, the agent automatically retries using a fallback provider. This is powered by [litellm.Router](https://docs.litellm.ai/docs/routing) and requires `datarobot-genai>=0.15.20`.

### Determining the primary model

The examples below use `{LLM_DEFAULT_MODEL}` as a placeholder for the primary model. To resolve it, run `bash -lc "grep '^LLM_DEFAULT_MODEL=' .env 2>/dev/null"` to get the value of `LLM_DEFAULT_MODEL`. Strip any leading `datarobot/` prefix from the value (e.g. `datarobot/vertex_ai/foo` → `vertex_ai/foo`), then replace `{LLM_DEFAULT_MODEL}` with the result. If the command returns nothing, use `azure/gpt-5-mini-2025-08-07`.

---

## DRAgent (workflow.yaml)

In `workflow.yaml`, replace the `datarobot-llm-component` block with `datarobot-llm-router` and define a `primary` and one or more `fallbacks`:

```yaml
llms:
  datarobot_llm:
    _type: datarobot-llm-router
    primary:
      llm_use_datarobot_llm_gateway: true
      llm_default_model: {LLM_DEFAULT_MODEL}
    fallbacks:
      - llm_use_datarobot_llm_gateway: true
        llm_default_model: anthropic/claude-opus-4-20250514
    num_retries: 1

workflow:
  _type: langgraph_agent  # or crewai_agent / llamaindex_agent / per_user_tool_calling_agent
  llm_name: datarobot_llm
```

The `workflow` block remains unchanged — only the `llms` block needs to be updated.

### LLMConfig fields

Each entry under `primary` and `fallbacks` is an `LLMConfig` with these fields:

| Field | Type | Description |
|---|---|---|
| `llm_use_datarobot_llm_gateway` | `bool` | `true` = route through DataRobot LLM Gateway (default). `false` = use a deployment or external provider. |
| `llm_default_model` | `str` | Model string (e.g. `azure/gpt-5-mini-2025-08-07`, `anthropic/claude-opus-4-20250514`). |
| `llm_deployment_id` | `str \| None` | DataRobot deployment ID when routing to a deployed LLM (overrides env). |
| `llm_nim_deployment_id` | `str \| None` | DataRobot deployment ID for NIM-based routing. |
| `datarobot_endpoint` | `str \| None` | Per-entry DataRobot endpoint URL override. |
| `datarobot_api_token` | `str \| None` | Per-entry API token override. |

### Router-level fields

| Field | Type | Default | Description |
|---|---|---|---|
| `num_retries` | `int` | `1` | Number of retries per model before moving to the next fallback. |

---

## How fallback works

When the primary model fails (network error, rate limit, model error), `litellm.Router` retries up to `num_retries` times, then moves to the next fallback in order. Each `LLMConfig` entry is independently translated to a litellm model entry, so primary and fallbacks can point to entirely different providers and models.
