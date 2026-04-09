# Skills

Skills are self-contained capability modules that extend what an agent can do. They appear in the **Skills** tab of an agent's detail view and in the global **Skills Library**.

---

## What is a skill?

A skill is a folder containing:

```
my-skill/
  SKILL.md          # Description, inputs, outputs, examples
  handler.py        # Execution logic
  mcp-tools.json    # MCP tool manifest (name, description, inputSchema)
```

When attached to an agent, the skill's tools become available to the SOUL during inference.

---

## Attaching a skill

1. Open **Agent Detail** → **Skills** tab.
2. Click **Attach Skill**.
3. Search the Skills Library or paste a Git URL.
4. Click **Attach** — the skill manifest is written to the agent's LRS configuration.
5. The agent picks up new tools on next session start.

!!! tip "Hot-attach"
    Running agents pick up newly attached skills within 5 seconds without a restart, via the heartbeat channel.

---

## Skills tab layout

```
┌────────────────────────────────────────────────────────────┐
│  Attached Skills                          [+ Attach Skill] │
├────────────────────────────────────────────────────────────┤
│  ● web-search          2 tools   [Detach] [View]           │
│  ● dr-deployment-mgr   5 tools   [Detach] [View]           │
│  ○ code-executor        inactive  [Enable] [Detach]         │
└────────────────────────────────────────────────────────────┘
```

---

## Skill status

| Status | Meaning |
|---|---|
| ● Active | Loaded and available to the SOUL |
| ○ Inactive | Attached but disabled (toggle to enable) |
| ⚠ Error | Handler failed to load; check logs |

---

## Writing a new skill

See the full [Skills Pipeline guide](../build/soul-reference.md) for step-by-step instructions on writing a `SKILL.md`, defining tools in `mcp-tools.json`, and submitting via the UI or MCP tools.

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../build/soul-reference/">
  <div class="next-step-card-title">Soul Reference</div>
  <div class="next-step-card-desc">Understand how skills integrate with SOUL.md.</div>
</a>
<a class="next-step-card" href="../cron-jobs/">
  <div class="next-step-card-title">Cron Jobs</div>
  <div class="next-step-card-desc">Schedule recurring tasks using attached skills.</div>
</a>
<a class="next-step-card" href="../../connect/mcp-tools/">
  <div class="next-step-card-title">MCP Tools</div>
  <div class="next-step-card-desc">Browse all 49 available MCP tools by category.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
