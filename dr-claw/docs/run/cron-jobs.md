# Cron Jobs

Schedule recurring tasks that run against any agent on a cron schedule. Cron jobs are useful for periodic data pulls, automated reports, or proactive monitoring.

---

## How it works

A cron job is a saved prompt + schedule that Soul Factory fires on your behalf:

```
Schedule: "0 9 * * 1-5"
Agent: nemoclaw
Prompt: "Summarise overnight DR deployment activity and post to Slack"
```

At the scheduled time, Soul Factory:

1. Opens a new session against the target agent.
2. Sends the prompt.
3. Streams the response into the **Cron History** log.
4. Optionally fires a webhook with the result.

---

## Creating a cron job

1. Navigate to **Agent Detail** → **Cron Jobs** tab (or **Run → Cron Jobs** from the nav).
2. Click **+ New Job**.
3. Fill in:

| Field | Description |
|---|---|
| **Name** | Human-friendly label |
| **Agent** | Target agent (must be RUNNING at trigger time) |
| **Prompt** | The message to send — supports `{{date}}`, `{{time}}` template vars |
| **Schedule** | Standard cron expression (5-field) |
| **Timeout** | Max seconds to wait for response (default 120) |
| **Webhook URL** | Optional POST target for the result |

4. Click **Save** — the job appears in the Scheduled Jobs table.

---

## Cron expression help

| Example | Meaning |
|---|---|
| `0 9 * * 1-5` | 09:00 Mon–Fri |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 1 * *` | Midnight on the 1st of each month |

---

## Template variables

| Variable | Resolves to |
|---|---|
| `{{date}}` | Today's date: `2026-04-09` |
| `{{time}}` | Current UTC time: `09:00:00` |
| `{{agent_name}}` | The agent's workload name |

---

## Job history

Each run is logged in the **Cron History** table:

| Column | Details |
|---|---|
| Timestamp | When the job fired |
| Status | `success` / `error` / `timeout` |
| Duration | Wall-clock ms |
| Response preview | First 140 chars of the agent's reply |
| Full response | Expandable |

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../chat/">
  <div class="next-step-card-title">Chat</div>
  <div class="next-step-card-desc">Understand the session model that cron jobs use.</div>
</a>
<a class="next-step-card" href="../../govern/fleet/">
  <div class="next-step-card-title">Fleet</div>
  <div class="next-step-card-desc">Monitor scheduled job activity across all agents.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
