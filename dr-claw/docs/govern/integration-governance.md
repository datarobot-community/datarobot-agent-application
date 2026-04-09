# Integration Governance

Manage every external connection your agents rely on — the Global MCP server, GitHub OAuth, DR LLM Gateway, and custom webhooks — from one secure admin page.

---

## Integration types

| Integration | What it does | Status |
|---|---|---|
| **Global MCP** | Provides 49 DR platform tools to all agents | Live (JWT auth) |
| **GitHub OAuth** | Enables soul hot-swap from PR branches | Mock (Cycle 2) |
| **DR LLM Gateway** | Routes LLM calls; provides billing | Live |
| **DR Workload API** | Agent lifecycle management | Live |
| **LRS** | Session and event log storage | Live |
| **OpenShell / Envoy** | Container log streaming | Mock (Cycle 2) |
| **Slack webhook** | HITL notifications | Mock (Cycle 2) |

---

## Global MCP

The Global MCP server is the backbone of Soul Factory — it exposes 49 DataRobot platform tools to every agent.

### JWT management

MCP connections are authenticated with short-lived JWTs (8-hour TTL):

```bash
# Re-generate JWT
python scripts/gen_mcp_jwt.py | tee .mcp_jwt
export MCP_JWT=$(cat .mcp_jwt)
```

In Cycle 2, the backend auto-rotates this JWT before expiry. You can monitor the current JWT status from this page:

| Field | Value |
|---|---|
| Status | ● Active |
| Issued | 2026-04-09 07:00 UTC |
| Expires | 2026-04-09 15:00 UTC |
| Scopes | `dr:read dr:write workload:manage` |

### MCP proxy

Soul Factory acts as an MCP proxy — it relays tool calls from the SOUL to the Global MCP server, adding auth headers and rate-limit handling. See [MCP Tools](../connect/mcp-tools.md) for the full tool catalogue.

---

## GitHub OAuth (Cycle 2)

GitHub OAuth allows agents to pull soul definitions directly from a GitHub branch, enabling a GitOps-style soul deployment workflow.

```
Developer pushes SOUL.md to branch `feat/new-persona`
         ↓
GitHub webhook fires to Soul Factory
         ↓
Soul Factory fetches branch SOUL.md via GitHub API
         ↓
New soul version deployed to agent (zero downtime)
```

Configuration (Cycle 2):

| Field | Value |
|---|---|
| OAuth App ID | From GitHub Developer Settings |
| Callback URL | `https://your-sf-instance/oauth/github/callback` |
| Scopes | `repo:read` |

---

## DR LLM Gateway

All LLM calls route through DR's gateway, which provides:

- **Model routing** — auto-select best model for request size
- **Cost tracking** — per-call billing to the cost ledger
- **Rate limiting** — per-agent token budgets
- **Fallback** — failover to secondary models on error

The gateway connection uses your `DATAROBOT_API_TOKEN`.

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../connect/mcp-tools/">
  <div class="next-step-card-title">MCP Tools</div>
  <div class="next-step-card-desc">Browse all 49 tools available via Global MCP.</div>
</a>
<a class="next-step-card" href="../../connect/setup/">
  <div class="next-step-card-title">Setup Guide</div>
  <div class="next-step-card-desc">Initial JWT and Workload ID configuration.</div>
</a>
<a class="next-step-card" href="../../reference/cycle-2/">
  <div class="next-step-card-title">Cycle 2 Roadmap</div>
  <div class="next-step-card-desc">When live integrations will replace mock stubs.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
