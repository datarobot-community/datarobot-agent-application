# Tracing and telemetry (DRAgent)

> **Also known as**: OpenTelemetry, OTel, observability, instrumentation, spans, monitoring, telemetry, trace export

Agents that use the DRAgent front server are instrumented for distributed tracing out of the box. Each agent run emits OpenTelemetry spans for LLM calls, tool invocations, HTTP requests, and framework-level steps, and exports them to DataRobot for monitoring on the **Monitoring > Data exploration** tab of the deployment. This is powered by [OpenTelemetry](https://opentelemetry.io/) and the `datarobot-genai` `dragent` extra — no extra setup is required in a generated agent.

Tracing is wired up by two pieces that the template generates automatically:

| Piece | File | What it does |
|---|---|---|
| [`instrument()` call](#instrumentation-agentagentregisterpy) | `agent/agent/register.py` | Patches HTTP clients, the OpenAI SDK, and the agent framework to emit spans. |
| [`otelcollector` block](#exporter-workflowyaml) | `agent/workflow.yaml` | Configures the OTel collector that exports those spans to DataRobot. |

Both are present by default and require no manual setup. This doc explains what they are, so they are not mistakenly removed, and how to recognize them.

## Instrumentation (`agent/agent/register.py`)

Near the top of `agent/agent/register.py`, `instrument()` from `datarobot_genai.core.telemetry.agent` is called right after the module imports:

```python
from datarobot_genai.core.telemetry.agent import instrument
# ... other module imports ...

# Instrumentation call is required to set up tracing and telemetry for agents.
instrument(framework="langgraph")
```

The call runs as the module loads, before the agent handles any requests, so the framework, HTTP clients, and the OpenAI SDK are instrumented and emit spans.

### The `framework` argument

`instrument()` takes an optional `framework` argument that matches the agent framework so framework-specific spans (chains, agents, tool calls) are captured. The template sets this automatically:

| Framework | Call generated in `register.py` | Framework spans via |
|---|---|---|
| Base (no framework) | `instrument()` | — |
| LangGraph | `instrument(framework="langgraph")` | `LangchainInstrumentor` |
| CrewAI | `instrument(framework="crewai")` | `CrewAIInstrumentor` |
| LlamaIndex | `instrument(framework="llamaindex")` | `LlamaIndexInstrumentor` |

`instrument()` also accepts `framework="nat"`, which instruments CrewAI, LangGraph, and LlamaIndex together.

### What gets instrumented

Regardless of framework, `instrument()` always:

- Patches HTTP clients — `requests`, `aiohttp`, and `httpx` — so outbound calls are traced.
- Patches the OpenAI SDK so LLM requests/responses become spans.
- Instruments `threading` so spans propagate across threads.
- Installs a global OpenTelemetry `TracerProvider` pointed at the DataRobot OTel ingest, so spans actually reach DataRobot.
- Opts out of unrelated third-party telemetry (for example, sets `RAGAS_DO_NOT_TRACK` and `DEEPEVAL_TELEMETRY_OPT_OUT`).

The call is idempotent — calling it more than once is safe; each client and framework is instrumented at most once.

## Exporter (`workflow.yaml`)

The `general.telemetry.tracing` section of `workflow.yaml` registers the collector that exports spans to DataRobot:

```yaml
general:
  telemetry:
    tracing:
      otelcollector:
        _type: datarobot_otelcollector
        project: "agent"
```

| Field | Value | Description |
|---|---|---|
| `_type` | `datarobot_otelcollector` | The DataRobot OTel collector plugin shipped in the `datarobot-genai` `dragent` extra. |
| `project` | `"agent"` | Logical project/service name traces are grouped under. |

## Local development vs. deployed

The DataRobot exporter only activates when the DataRobot deployment environment is present. In local development (`task run` / the dev server), `instrument()` detects that the deployment env is incomplete and the tracer provider silently no-ops — the agent runs normally, but traces aren't exported. Full traces appear once the agent is deployed to DataRobot.

## View traces

For a deployed agent, open the **Monitoring > Data exploration** tab of the deployment to see end-to-end request traces, including LLM calls, tool invocations, and agent actions. See [Debugging deployed agents](./debugging.md#debugging-deployed-agents) and the [DataRobot tracing documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html).

## Disable tracing

Tracing is on by default and recommended. To disable it, remove the `instrument()` block from `agent/agent/register.py` and the `telemetry` block from `agent/workflow.yaml`. Removing this code disables all monitoring, tracing, and telemetry for the agent.
