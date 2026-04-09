# My Agents

The **My Agents** page is your home base — a card grid showing every agent you own or have access to, with real-time status badges and one-click launch controls.

---

## Layout

```
┌────────────────────────────────────────────────────────────┐
│  Search _______________   [+ New Agent]    Filter ▼        │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ nemoclaw     │  │ data-analyst │  │ code-review  │     │
│  │ ● RUNNING    │  │ ○ STOPPED    │  │ ⚠ FAILED     │     │
│  │ Pack: core   │  │ Pack: data   │  │ Pack: dev    │     │
│  │ [Open] [···] │  │ [Start][···] │  │ [Logs] [···] │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────────────────────────────────────────┘
```

---

## Agent card anatomy

Each card shows:

| Element | Description |
|---|---|
| **Name** | Workload name pulled from DR Workload API |
| **Status badge** | Live-polled every 15 s (RUNNING / STOPPED / FAILED / STARTING) |
| **Pack** | The domain pack this agent uses |
| **Primary action** | Context-sensitive: `Open Chat`, `Start`, `View Logs` |
| **⋯ menu** | Edit soul, duplicate, delete, view raw workload |

---

## Starting an agent

1. Find the agent card.
2. Click **Start** — Soul Factory calls `POST /workloads/{id}/start` against DR Workload API.
3. The status badge animates to `STARTING`; after 30–90 s it transitions to `RUNNING`.
4. Click **Open Chat** to begin a session.

!!! note "Cycle 1 mock data"
    In Cycle 1, the agent list is populated from `mock-data/agents.js`. Real DR Workload API polling arrives in [Cycle 2](../reference/cycle-2.md).

---

## Creating a new agent

Click **+ New Agent** → the Configure Wizard opens. See [Configure Wizard](../build/configure.md) for field-by-field guidance.

---

## Filtering and search

| Filter | What it does |
|---|---|
| Search box | Fuzzy-matches agent names |
| Status filter | RUNNING / STOPPED / ALL |
| Pack filter | Narrows to a specific domain pack |

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="agent-detail/">
  <div class="next-step-card-title">Agent Detail</div>
  <div class="next-step-card-desc">Drill into logs, cost, skills, and chat for one agent.</div>
</a>
<a class="next-step-card" href="chat/">
  <div class="next-step-card-title">Chat</div>
  <div class="next-step-card-desc">How the live SSE chat loop works end to end.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
