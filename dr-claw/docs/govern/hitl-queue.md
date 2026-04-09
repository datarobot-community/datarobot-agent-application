# HITL Queue

The **HITL Queue** (Human-in-the-Loop Queue) collects every agent action that requires human approval before it can proceed. Agents pause and wait — for up to the configured timeout — until an operator approves or rejects.

---

## Why HITL?

Some agent actions are high-risk, irreversible, or require authorisation:

- Deploying a DR model to production
- Deleting a dataset
- Sending an external email or Slack message
- Executing code that modifies infrastructure

The SOUL.md author marks these action types as `hitl: required`. The runtime intercepts the tool call and creates a queue item.

---

## Queue table

```
┌──────────────┬───────────────────────────┬───────────┬──────────┬────────────┐
│  Agent       │  Action                   │  Triggered│  Timeout │  Action    │
├──────────────┼───────────────────────────┼───────────┼──────────┼────────────┤
│  nemoclaw    │ deploy_model prod-env      │  4 min ago│  26 min  │ ✓ Approve  │
│              │                           │           │          │ ✗ Reject   │
│  data-analyst│ delete_dataset raw_2024Q1 │  12 min   │  18 min  │ ✓ Approve  │
│              │                           │           │          │ ✗ Reject   │
└──────────────┴───────────────────────────┴───────────┴──────────┴────────────┘
```

---

## Queue item anatomy

Each item shows:

| Field | Description |
|---|---|
| **Agent** | Which agent triggered the pause |
| **Action** | MCP tool name + arguments |
| **Context** | The last N messages leading up to the trigger |
| **Triggered** | How long ago the item entered the queue |
| **Timeout** | How long before the agent auto-rejects and continues |

---

## Approving or rejecting

1. Read the **Context** section to understand why the agent wants to take this action.
2. Click **Approve** to let the agent proceed with the tool call.
3. Click **Reject** to cancel the tool call. You may optionally add a rejection note — the agent receives this as part of the conversation context.

!!! warning "Timeout behaviour"
    If no decision is made before the timeout, the action is **auto-rejected** and the agent resumes with an error note. The default timeout is 30 minutes, configurable per SOUL.md.

---

## Configuring HITL in SOUL.md

```yaml
# In your SOUL.md frontmatter:
hitl:
  enabled: true
  timeout_minutes: 30
  require_for:
    - dr_deploy_model
    - dr_delete_dataset
    - send_email
```

---

## Notifications

When a HITL item enters the queue:

- **In-app** — a badge appears on the HITL Queue nav item
- **Email** (Cycle 2) — configured operators receive an email
- **Slack** (Cycle 2) — posts to a configured channel

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../fleet/">
  <div class="next-step-card-title">Fleet</div>
  <div class="next-step-card-desc">See which agents currently have pending HITL items.</div>
</a>
<a class="next-step-card" href="../../run/chat/">
  <div class="next-step-card-title">Chat</div>
  <div class="next-step-card-desc">How HITL pauses appear in the chat interface.</div>
</a>
<a class="next-step-card" href="../../build/soul-reference/">
  <div class="next-step-card-title">Soul Reference</div>
  <div class="next-step-card-desc">Configure HITL triggers in SOUL.md.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
