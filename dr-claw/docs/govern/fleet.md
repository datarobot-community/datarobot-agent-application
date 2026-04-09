# Fleet

The **Fleet** page gives admins a bird's-eye view of every Soul Factory agent across all workspaces — status, pack, soul version, and recent activity.

---

## Fleet table

```
┌────────────────────────────────────────────────────────────────────────┐
│  Fleet                                     Search ________  Filter ▼   │
├──────────────────┬───────────┬──────────┬───────────┬──────────────────┤
│  Agent           │  Status   │  Pack    │  Soul     │  Last Active     │
├──────────────────┼───────────┼──────────┼───────────┼──────────────────┤
│  nemoclaw        │ ● RUNNING │ core     │ v2.1      │  2 min ago       │
│  data-analyst    │ ○ STOPPED │ data     │ v1.4      │  3 hours ago     │
│  code-review     │ ⚠ FAILED  │ dev      │ v1.0      │  23 min ago      │
└──────────────────┴───────────┴──────────┴───────────┴──────────────────┘
```

---

## Columns

| Column | Source | Notes |
|---|---|---|
| Agent | DR Workload API | Name from workload config |
| Status | Workload API poll | Refreshed every 15 s |
| Pack | SOUL.md header | Cached in LRS |
| Soul version | LRS blob version | Latest deployed |
| Last Active | LRS session log | Time of last message |

---

## Bulk actions

Select multiple agents (checkbox) to:

- **Stop all** — gracefully stop selected workloads
- **Restart all** — stop then start
- **Export CSV** — download fleet snapshot for auditing

---

## Filters

| Filter | Options |
|---|---|
| Status | RUNNING / STOPPED / FAILED / ALL |
| Pack | core / data / dev / custom / ALL |
| Workspace | Any workspace you have access to |

---

## Health indicators

The Fleet page also surfaces:

- **HITL backlog** — number of pending approvals across all agents
- **Error rate** — % of messages that returned errors in the last hour
- **Avg response latency** — p50 across the fleet

!!! note "Cycle 1"
    Fleet uses mock data. Live Workload API polling is wired in [Cycle 2](../reference/cycle-2.md).

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../hitl-queue/">
  <div class="next-step-card-title">HITL Queue</div>
  <div class="next-step-card-desc">Review and resolve pending human approvals.</div>
</a>
<a class="next-step-card" href="../logs/">
  <div class="next-step-card-title">Logs</div>
  <div class="next-step-card-desc">Aggregate log stream across all fleet agents.</div>
</a>
<a class="next-step-card" href="../cost-usage/">
  <div class="next-step-card-title">Cost & Usage</div>
  <div class="next-step-card-desc">Fleet-wide LLM spend and token breakdown.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
