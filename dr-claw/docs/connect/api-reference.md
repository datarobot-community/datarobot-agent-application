# API Reference

All integration points for the Soul Factory UI. Base URLs vary by environment — staging uses LRS endpoints.

---

## Global MCP

**Base URL:** `https://beta-global-mcp.stg.ue1.aws.int.datarobot.com/mcp`

**Auth:** Bearer JWT (short-lived OAuth token). Patched via `dr-claw/patch-nginx.sh`.

### Tools

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/mcp/tools?agent_id={id}` | Per-agent active tool list with health status |
| `PATCH` | `/mcp/tools/{tool_id}` | Enable/disable a tool: `{ enabled: false, agent_id }` |

### Skills / Resources

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/mcp/resources` | All available skills with name, version, description, install status |
| `GET` | `/mcp/resources?installed=true&agent_id={id}` | Skills installed for a specific agent |
| `POST` | `/mcp/resources` | Submit a new skill: `{ skill_md, mcp_tools_json }` → returns `{ pipeline_job_id }` |
| `GET` | `/mcp/resources/{id}/status` | Pipeline status: `submitted` → `validating` → `e2e-testing` → `pending-approval` → `approved` |
| `POST` | `/mcp/resources/{skill_id}/install` | Install a skill into an agent: `{ agent_id }` |
| `PUT` | `/mcp/resources/{skill_id}` | Update skill — triggers pipeline re-run |

### Integration Governance

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/mcp/integrations` | Approved integrations with health status |
| `GET` | `/mcp/integrations/pending` | Submissions pending approval |
| `POST` | `/mcp/integrations/{id}/approve` | Promote to Global MCP |
| `POST` | `/mcp/integrations/{id}/reject` | Reject with `{ reason }` |

---

## DR Workload API / LRS

Used for agent lifecycle — launch, monitor, pause, stop.

### Agent Lifecycle

| Method | Endpoint | Usage |
|--------|----------|-------|
| `POST` | `/api/v2/workloads` | Launch agent: `{ pack, soul_url, mcp_server_url, dr_token, interface: 'slack\|web' }` → returns `{ id, status: 'provisioning' }` |
| `GET` | `/api/v2/workloads/{id}/status` | Poll during launch. Status: `provisioning` → `starting` → `healthy` |
| `GET` | `/api/v2/workloads` | All agents (admin scope — Fleet page) |
| `GET` | `/api/v2/workloads?owner=current_user` | Current user's agents (My Agents page) |
| `GET` | `/api/v2/workloads/{id}` | Agent detail — health, uptime, container status |
| `POST` | `/api/v2/workloads/{id}/pause` | Pause agent |
| `DELETE` | `/api/v2/workloads/{id}` | Stop and remove agent (requires confirm dialog) |

### Cron Jobs

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/workloads/{id}/crons` | Configured schedules — last run, next run, last output |
| `PATCH` | `/api/v2/workloads/{id}/crons/{cron_id}` | Toggle cron: `{ enabled: bool }` (no redeploy) |

### Anomaly Detection

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/workloads/{id}/anomalies` | Flagged events — used by Fleet page anomaly badge |

---

## Envoy / OpenShell Log Streams

SSE streams for Agent Detail and Logs pages.

### Agent-scoped logs

```
GET /api/v2/workloads/{id}/logs?stream=true
```

Each SSE event is structured JSON:

```json
{
  "timestamp": "2026-04-09T06:00:00Z",
  "type": "ALLOW|BLOCK|LLM|HITL|CRON",
  "tool": "tavily_search",
  "latency": "342ms",
  "tokens": 1200,
  "cost": 0.0024,
  "reason": ""
}
```

### Org-wide logs (admin)

```
GET /api/v2/logs?stream=true&agent_id={optional}&event_type={optional}
```

Same event shape, plus `agent_id` and `agent_name` fields.

**Event type filter values:** `BLOCK`, `ALLOW`, `LLM`, `HITL`, `CRON`

---

## DR LLM Gateway

All model calls route through the gateway. The UI reads cost and token data — it doesn't call the gateway directly.

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/llm-gateway/usage?scope=org&period=month` | Org-wide cost — Cost & Usage page |
| `GET` | `/api/v2/llm-gateway/usage?scope=org&period=7d&group_by=day` | 7-day chart data |
| `GET` | `/api/v2/llm-gateway/usage?agent_id={id}&period=today` | Per-agent cost — Agent Detail metrics |
| `GET` | `/api/v2/llm-gateway/aliases` | Current sota/large/mid model alias mappings *(future)* |

**Usage response shape:**

```json
{
  "total_cost": 1240.50,
  "total_runs": 8420,
  "total_tokens": 12400000,
  "by_agent": [
    { "agent_id": "...", "agent_name": "...", "pack": "supply-chain", "tokens": 7400000, "cost": 740.00, "primary_model": "sota" }
  ]
}
```

---

## HITL Queue

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/hitl/queue` | All pending write operations |
| `POST` | `/api/v2/hitl/queue/{id}/approve` | Release the write op — agent executes |
| `POST` | `/api/v2/hitl/queue/{id}/reject` | Reject: `{ reason }` — agent receives rejection |
| `POST` | `/api/v2/hitl/queue/{id}/clarify` | Send message to agent: `{ message }` — card stays in queue |
| `GET` | `/api/v2/hitl/audit` | Full audit log of past approvals and rejections |

**Queue item shape:**

```json
{
  "id": "...",
  "agent_id": "...",
  "agent_name": "CFDS Agent",
  "user": "marcos.r",
  "action": "Write CRM note",
  "tool": "salesforce.create_note",
  "content_preview": "Meeting summary: discussed Q2 forecast...",
  "timestamp": "2026-04-09T14:32:00Z"
}
```

---

## Heartbeat & Channels *(Cycle 2)*

### Heartbeat

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/workloads/{id}/heartbeat/config` | Interval, active hours, on/off |
| `PATCH` | `/api/v2/workloads/{id}/heartbeat/config` | Update schedule |
| `GET` | `/api/v2/workloads/{id}/heartbeat/last` | Last heartbeat output summary |

### Channels

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/api/v2/workloads/{id}/channels` | Slack, webhook, email configs |
| `PATCH` | `/api/v2/workloads/{id}/channels/{channel}` | Update per-channel config |

---

## GitHub OAuth *(Cycle 2)*

Used by the **Get the Repo** page to fork the `openclaw-agent` template.

| Method | Endpoint | Usage |
|--------|----------|-------|
| `GET` | `/oauth/github/authorize` | Initiates GitHub OAuth consent flow |
| `POST` | `/oauth/github/fork` | Forks template repo: `{ repo: 'openclaw-agent', pack, target_user, dr_token, mcp_url }` → `{ fork_url }` |

**Blocked on:** OAuth callback endpoint on the DR backend.

---

## MCP Proxy

**Current:** `MCP_PROXY_URL = '/agents/mcp'` — requires nginx JWT patch.

**Cycle 2 target:** When MCP team adds DR API token support:
```js
// agents/api/mcp-config.js
export const MCP_PROXY_URL = '/api/v2/agents/mcp-proxy/';
```

That's the only change — no nginx patch, no rebuild beyond this one constant.

**Blocked on:** MCP team shipping `Authorization: Token <dr_api_token>` support.
