# Logs

The **Logs** page aggregates real-time log output from all agents in your fleet — OpenShell container logs and LRS structured events in a single, searchable, filterable stream.

---

## Log sources

| Source | What it contains |
|---|---|
| **OpenShell / Envoy** | Container stdout/stderr, HTTP access logs |
| **LRS Events** | Structured Soul events: tool calls, HITL triggers, session starts/ends, errors |
| **DR LLM Gateway** | LLM call latency, token counts, model used (Cycle 2) |

---

## Log viewer

```
┌────────────────────────────────────────────────────────────────┐
│  Search ____________  [Agent ▼]  [Level ▼]  [Source ▼]  Live ● │
├──────────┬─────────┬──────────┬────────────────────────────────┤
│ 09:14:22 │ nemoclaw│ INFO     │ Session started: sess_abc123   │
│ 09:14:23 │ nemoclaw│ TOOL_CALL│ dr_list_deployments {limit:10} │
│ 09:14:24 │ nemoclaw│ INFO     │ Tool result: 3 deployments     │
│ 09:14:31 │ nemoclaw│ HITL     │ deploy_model triggered → queue │
│ 09:15:02 │ data-a  │ ERROR    │ LLM timeout after 30s          │
└──────────┴─────────┴──────────┴────────────────────────────────┘
```

---

## Log levels

| Level | Color | Meaning |
|---|---|---|
| `INFO` | Gray | Normal operation |
| `TOOL_CALL` | Lavender | MCP tool invoked |
| `TOOL_RESULT` | Dim lavender | Tool response received |
| `HITL` | Amber | Human approval triggered |
| `WARN` | Amber | Non-fatal issue |
| `ERROR` | Red | Error; agent may have paused |
| `DEBUG` | Dim gray | Verbose; disabled by default |

---

## Filtering

| Filter | Options |
|---|---|
| Search | Keyword / regex |
| Agent | Any specific agent or ALL |
| Level | INFO / TOOL_CALL / HITL / ERROR / ALL |
| Source | OpenShell / LRS / ALL |
| Time range | Last 15m / 1h / 6h / 24h / Custom |

---

## Expanding a log line

Click any log line to expand its full JSON payload:

```json
{
  "ts": "2026-04-09T09:14:23Z",
  "agent": "nemoclaw",
  "level": "TOOL_CALL",
  "source": "lrs",
  "event": {
    "tool": "dr_list_deployments",
    "args": {"status": "RUNNING", "limit": 10},
    "session_id": "sess_abc123",
    "trace_id": "tr_xyz789"
  }
}
```

---

## Downloading logs

Click **Export** (top-right) to download the current filtered view as NDJSON or CSV. Useful for incident post-mortems or audit trails.

!!! note "Cycle 1"
    Logs page renders mock JSON in Cycle 1. Live SSE streaming via `/workloads/{id}/logs/stream` is wired in [Cycle 2](../reference/cycle-2.md).

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../fleet/">
  <div class="next-step-card-title">Fleet</div>
  <div class="next-step-card-desc">Cross-agent status at a glance.</div>
</a>
<a class="next-step-card" href="../cost-usage/">
  <div class="next-step-card-title">Cost & Usage</div>
  <div class="next-step-card-desc">Token and spend analytics to complement logs.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
