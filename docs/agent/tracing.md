# Tracing and telemetry (DRAgent)

> **Also known as:** OpenTelemetry, OTel, observability, instrumentation, spans, monitoring, telemetry, trace export

Agents that use the **DRAgent** front server are instrumented for distributed tracing out of the box. Each agent run emits OpenTelemetry spans for LLM calls, tool invocations, HTTP requests, and framework-level steps, and exports them to DataRobot for monitoring on the deployment's **Monitoring > Data exploration** tab. This is powered by [OpenTelemetry](https://opentelemetry.io/) and the `datarobot-genai` `dragent` extra — no extra setup is required in a generated agent.

Tracing is wired up by two pieces that the template generates automatically:

| Piece | File | What it does |
|---|---|---|
| [`instrument()` call](#instrumentation-agentregisterpy) | `agent/register.py` | Patches HTTP clients, the OpenAI SDK, and the agent framework to emit spans. |
| [`otelcollector` block](#exporter-workflowyaml) | `workflow.yaml` | Configures the OTel collector that exports those spans to DataRobot. |

Both are present by default. You do not need to add them — this doc explains what they are so you know not to remove them and how to recognize them.

> [!NOTE]
> Tracing as described here applies to the **DRAgent** front server (`_type: dragent_fastapi`). For DRUM-based agents, see [Implement tracing](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html).

---

## Instrumentation (`agent/register.py`)

Near the top of `agent/register.py`, `instrument()` from `datarobot_genai.core.telemetry_agent` is called right after the module imports:

```python
from datarobot_genai.core.telemetry_agent import instrument
# ... other module imports ...

# INSTRUMENTATION CALL IS REQUIRED TO SETUP TRACING AND TELEMETRY FOR AGENTS
instrument(framework="langgraph")
```

The call runs as the module loads, before the agent handles any requests, so the framework, HTTP clients, and the OpenAI SDK are instrumented and emit spans.

### The `framework` argument

`instrument()` takes an optional `framework` argument that matches the agent's framework so framework-specific spans (chains, agents, tool calls) are captured. The template sets it for you:

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
- Opts out of unrelated third-party telemetry (e.g., sets `RAGAS_DO_NOT_TRACK`, `DEEPEVAL_TELEMETRY_OPT_OUT`).

The call is **idempotent** — calling it more than once is safe; each client and framework is instrumented at most once.

---

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

---

## Local development vs. deployed

The DataRobot exporter only activates when the DataRobot deployment environment is present. In local development (`task run` / the dev server), `instrument()` detects that the deployment env is incomplete and the tracer provider **silently no-ops** — your agent runs normally, you just won't see traces exported. Full traces appear once the agent is deployed to DataRobot.

## Viewing traces

For a deployed agent, open the deployment's **Monitoring > Data exploration** tab to see end-to-end request traces, including LLM calls, tool invocations, and agent actions. See [Debugging deployed agents](./debugging.md#debugging-deployed-agents) and the [DataRobot tracing documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html).

## Disabling tracing

Tracing is on by default and recommended. To disable it, remove the `instrument()` block from `agent/register.py` **and** the `telemetry` block from `workflow.yaml`. Removing this code disables all monitoring, tracing, and telemetry for the agent.
