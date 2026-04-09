# Agent Detail

Clicking an agent card opens its detail view — a tabbed page with everything you need to understand, interact with, and manage a single agent.

---

## Tabs

| Tab | What's inside |
|---|---|
| **Overview** | Status, workload metadata, active soul, pack |
| **Chat** | Live SSE chat interface |
| **Skills** | Attached skills list + attach/detach controls |
| **Logs** | Streaming log tail from OpenShell / Envoy |
| **Cost** | Token usage, LLM cost breakdown, time chart |

---

## Overview tab

```
┌────────────────────────────────────────────────────────────┐
│  nemoclaw                                    ● RUNNING     │
│  Workload ID: wl_abc123                                    │
│  Pack: core-assistant  Soul: SOUL.md v2.1                 │
├────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ 1,243 msgs  │  │ $0.42 today │  │ 42 s avg    │        │
│  │ All time    │  │ LLM cost    │  │ Response    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└────────────────────────────────────────────────────────────┘
```

Key fields:

| Field | Source |
|---|---|
| Workload ID | DR Workload API |
| Status | Polled every 15 s |
| Active soul | LRS blob name |
| Pack | Embedded in SOUL.md header |
| Messages | LRS session log count |
| Cost today | LLM Gateway billing ledger |
| Avg response | LRS p50 latency |

---

## Logs tab

The Logs tab streams real-time output from two sources:

1. **OpenShell** — container stdout/stderr via Envoy proxy
2. **LRS events** — structured Soul events (tool calls, HITL triggers, errors)

Log levels are colour-coded:

| Level | Color |
|---|---|
| `INFO` | Default text |
| `TOOL_CALL` | Lavender |
| `HITL_TRIGGER` | Amber |
| `ERROR` | Red |

Use the search box to filter by keyword. Click any log line to expand the full JSON payload.

!!! note "Cycle 1"
    Logs tab renders mock JSON in Cycle 1. Live streaming via SSE `/workloads/{id}/logs/stream` is wired in [Cycle 2](../reference/cycle-2.md).

---

## Cost tab

Shows:

- **Daily cost** — LLM Gateway billing for this agent over the selected period
- **Token breakdown** — input vs output vs cached tokens
- **Model mix** — which LLM models were called and how often
- **Hourly chart** — cost over time (bar chart)

!!! note "Cycle 1"
    Cost tab uses mock data. Real billing from DR LLM Gateway arrives in Cycle 2.

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../chat/">
  <div class="next-step-card-title">Chat</div>
  <div class="next-step-card-desc">Deep dive into the SSE chat message lifecycle.</div>
</a>
<a class="next-step-card" href="../skills/">
  <div class="next-step-card-title">Skills</div>
  <div class="next-step-card-desc">Attach skills to extend your agent's capabilities.</div>
</a>
<a class="next-step-card" href="../../govern/logs/">
  <div class="next-step-card-title">Fleet Logs</div>
  <div class="next-step-card-desc">Aggregate logs across all agents from the Govern section.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
