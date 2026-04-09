# Cycle 2 Roadmap

Cycle 1 built all 11 pages with mock data and live wiring wherever possible. Cycle 2 replaces mock with real API calls, wires missing flows, and aligns components with the DR design system.

---

## Priority Order

| # | Item | Blocked On |
|---|------|------------|
| 1 | Real Workload API — agent list + launch + detail | Nothing |
| 2 | Real SSE log stream | Envoy access |
| 3 | Skills pipeline — real MCP calls | MCP `create_skill` tool |
| 4 | Agent Detail — per-agent tool list + toggle | Workload API done |
| 5 | Cost — real LLM Gateway data | LLM Gateway API access |
| 6 | HITL clarify flow + audit log | HITL API |
| 7 | Integration Governance — real API | MCP integrations endpoints |
| 8 | dr-soul chat wiring | dr-soul API contract |
| 9 | MCP proxy migration | MCP team ships token auth |
| 10 | GitHub OAuth — Get the Repo real fork | DR backend OAuth endpoint |
| 11 | Design system component swap | Nothing — can do anytime |
| 12 | Heartbeat + Channels tabs | Workload API done |

---

## 1. Real Workload API

**Currently:** All agent data comes from `MOCK_AGENTS` in `client/js/agents/mock-data/agents.js`.

### My Agents
Replace `MOCK_AGENTS` with `GET /api/v2/workloads?owner=current_user`.

Normalize response to the existing agent object shape:
```js
agent = {
  id: workload.id,
  name: workload.name,
  packName: workload.labels?.pack || '—',
  status: workload.status,        // map to 'running' | 'stopped' | 'error'
  owner: workload.owner_username,
  runsTotal: workload.run_count,
  runsToday: workload.run_count_today,
  costMtd: workload.cost_mtd,
  lastRunAt: workload.last_run_at,
  endpoint: workload.url,
  workloadId: workload.id,
}
```

!!! note
    Field names are guesses — confirm against actual API response before wiring.

### Fleet
Replace `ALL_FLEET` with `GET /api/v2/workloads` (admin scope).
Anomaly data from `GET /api/v2/workloads/{id}/anomalies`.

### Launching
Replace `setTimeout` animation with a real poll:
```
POST /api/v2/workloads
  body: { pack, soul_url, mcp_server_url, dr_token, interface }
  → { id, status: 'provisioning' }

Poll: GET /api/v2/workloads/{id}/status  every 2s
  → provisioning → starting → healthy
```
Map each status transition to a step completion. On `healthy`: show real URL, stop polling.

### Pause / Stop
Wire to `POST /api/v2/workloads/{id}/pause` and `DELETE /api/v2/workloads/{id}`.
DELETE requires a confirm dialog.

**Files to touch:**
- `my-agents/my-agents-page.js`
- `fleet/fleet-page.js`
- `launching/launching-page.js`
- `my-agents/agent-detail/agent-detail-page.js`
- New: `agents/api/hooks.js` — `useWorkloads()`, `useWorkload(id)`, `useLaunchAgent()`, `usePauseAgent()`, `useStopAgent()`

---

## 2. Real SSE Log Stream

**Currently:** `setInterval` generates random events every 1.8s. No real data.

### Org-wide Logs Page
Replace `setInterval` with `GET /api/v2/logs?stream=true&agent_id={optional}&event_type={optional}`.

Each SSE event is JSON — maps directly to existing `EventBadge` colors. Filter params map to existing dropdowns. No UI changes needed, just data source swap.

### Agent Detail Logs Tab
Add a new Logs tab to Agent Detail:
- Stream: `GET /api/v2/workloads/{id}/logs?stream=true`
- Auto-scroll to bottom, pause on hover
- Filter by event type only (agent is already scoped)
- Navigate with `location.state.tab = 'logs'` from Fleet anomaly click-through

**Files to touch:**
- `logs/logs-page.js`
- New: `my-agents/agent-detail/tabs/logs-tab.js`
- `my-agents/agent-detail/agent-detail-page.js`
- `fleet/fleet-page.js` — pass anomaly event ID in navigate state

---

## 3. Skills Pipeline — Real MCP Calls

**Currently:** Submit a Skill runs a `setTimeout` simulation. No real API call.

### Submit
```
POST /mcp/resources
  body: { skill_md: "...", mcp_tools_json: {...} }
  → { pipeline_job_id }
```

### Poll Pipeline Status
```
GET /mcp/resources/{pipeline_job_id}/status  every 3s
  → { status: 'submitted'|'validating'|'e2e-testing'|'pending-approval'|'approved'|'rejected' }
```
Map status to existing `PipelineBar` stage index. Stop polling at `pending-approval`, `approved`, or `rejected`.

### Install Skill
Add Install button to Available tab cards:
```
POST /mcp/resources/{skill_id}/install
  body: { agent_id }
  → invalidate useMcpTools({ agentId })
```
Button state: idle → loading → installed.

**Files to touch:**
- `skills/skills-page.js` (SubmitTab + AvailableTab)
- `agents/api/hooks.js` — add `useCreateSkill()`, `usePipelineStatus(jobId)`, `useInstallSkill()`

---

## 4. Agent Detail — Per-Agent Tool List + Toggle

**Currently:** Tools tab fetches all 49 org-wide tools regardless of which agent is open.

### Per-agent list
```
GET /mcp/tools?agent_id={id}
  → [{ name, description, inputSchema, enabled: bool, health: 'ok'|'degraded'|'error', last_call_at }]
```
Add health dot to each tool row.

### Enable/disable toggle
```
PATCH /mcp/tools/{tool_id}
  body: { enabled: false, agent_id }
```
Optimistic update — flip toggle immediately, revert on error.

**Files to touch:**
- `my-agents/agent-detail/tabs/tools-tab.js` — pass `agentId`, add health dot + toggle
- `agents/api/hooks.js` — update `useMcpTools({ agentId })` to use `?agent_id=` param

---

## 5. Cost — Real LLM Gateway Data

**Currently:** `MOCK_COST_DATA` and `MOCK_COST_TOTALS` from a static file.

```
GET /api/v2/llm-gateway/usage?scope=org&period=month   → page metrics + table
GET /api/v2/llm-gateway/usage?scope=org&period=7d&group_by=day  → chart data (7 entries)
GET /api/v2/llm-gateway/usage?agent_id={id}&period=today  → Agent Detail header metrics
```

Chart component is unchanged — just replace the hardcoded `DAILY_DATA` array.

**Files to touch:**
- `cost/cost-page.js`
- `my-agents/agent-detail/agent-detail-page.js`

---

## 6. HITL Clarify Flow + Audit Log

**Currently:** Approve and Reject work (mock). No Clarify. No audit log.

### Clarify flow
Add Clarify button to each HITL card. Opens inline textarea → `POST /api/v2/hitl/queue/{id}/clarify { message }`. Agent responds via SSE or poll. Response appears inline. Card stays in queue until Approve or Reject.

Card states: `idle` → `clarifying` → `awaiting_response` → `response_received` → back to `idle`.

### Audit log
New "Audit Trail" section at bottom of HITL Queue page:
```
GET /api/v2/hitl/audit
  → [{ id, agent_name, action, tool, content_preview, decided_by, decided_at, outcome, agent_response }]
```
Table: Agent · Action · Tool · Decided By · When · Outcome. Click row → expand full content + agent response.

**Files to touch:**
- `hitl-queue/hitl-queue-page.js`

---

## 7. Integration Governance — Real API

**Currently:** 6 hardcoded approved integrations, 1 hardcoded pending (Salesforce). Mutations are local state only.

```
GET /mcp/integrations           → approved list with health
GET /mcp/integrations/pending   → pending submissions
POST /mcp/integrations/{id}/approve
POST /mcp/integrations/{id}/reject  body: { reason }
```

**Files to touch:**
- `integration-governance/integration-governance-page.js`
- `agents/api/hooks.js` — add `useIntegrations()`, `usePendingIntegrations()`, `useApproveIntegration()`, `useRejectIntegration()`

---

## 8. dr-soul Chat Wiring

**Currently:** Chat POSTs to relative `/v1/chat/completions`. Works when embedded inside a nemoclaw workload, not for dr-soul deployments.

Build `useAgentApi(agent)` abstraction that returns `{ sendMessage }` regardless of backend type:
```js
if (agent.backendType === 'workload') {
  // POST /api/v2/workloads/{workloadId}/v1/chat/completions
  // OpenAI-compatible SSE — already works
} else if (agent.backendType === 'deployment') {
  // POST /api/v2/deployments/{deploymentId}/predictions
  // Format TBD — pending dr-soul API contract
}
```

**Blocked on:** dr-soul team confirming API format (OpenAI-compatible or DR `/predictions` format).

**Files to touch:**
- `agents/api/use-agent-chat.js`
- New: `agents/api/hooks.js` — add `useAgentApi(agent)`
- `my-agents/agent-detail/tabs/chat-tab.js`

---

## 9. MCP Proxy Migration

**Currently:** `MCP_PROXY_URL = '/agents/mcp'` — requires nginx JWT patch every ~24h.

**Cycle 2:** One constant change:
```js
// agents/api/mcp-config.js
export const MCP_PROXY_URL = '/api/v2/agents/mcp-proxy/';
```

No nginx patch, no rebuild beyond this one line.

**Blocked on:** MCP team shipping `Authorization: Token <dr_api_token>` support.

---

## 10. GitHub OAuth — Get the Repo Real Fork

**Currently:** Shows instructions and a GitHub handle input. Doesn't fork.

```
GET /oauth/github/authorize  → GitHub OAuth consent
POST /oauth/github/fork
  body: { repo: 'openclaw-agent', pack, target_user, dr_token, mcp_url }
  → { fork_url }
```

After fork: show link to forked repo + pre-filled clone command.

**Blocked on:** OAuth callback endpoint on the DR backend.

**Files to touch:**
- `get-repo/get-repo-page.js`

---

## 11. Design System Component Swap

Low visual impact but required for production quality.

| Component | Current | Target |
|-----------|---------|--------|
| Tables | Raw `<table>` | `TableReact` from `@datarobot/design-system/table-react` |
| Buttons | `.claw-btn` | Design system `Button` |
| Empty states | `.claw-empty-state` | `EmptyStateWrapper` |
| Skeletons | Custom opacity-fade | `Skeleton` from `@datarobot/design-system/skeleton` |
| Toggles | Custom `<button>` toggle | `TogglerSwitch` from `@datarobot/design-system/toggler-switch` |

**Recommended order:** `TogglerSwitch` and `EmptyStateWrapper` first (smallest blast radius). `Button` last (every page).

---

## 12. Heartbeat + Channels Tabs

Both currently show "Coming Soon."

### Heartbeat tab
- HEARTBEAT.md editor (same pattern as Soul tab)
- Config: interval (hourly/daily/weekly), active hours (e.g. 06:00–22:00 UTC), on/off toggle
- Status: last heartbeat timestamp, last output summary, next scheduled
- API: `GET/PATCH /api/v2/workloads/{id}/heartbeat/config` + `GET /api/v2/workloads/{id}/heartbeat/last`

### Channels tab
- Slack config card: workspace, channel, bot token (masked), test connection button
- Webhook config card: URL, secret, event type checkboxes (`pr_opened`, `cron_trigger`, `hitl_request`)
- API: `GET/PATCH /api/v2/workloads/{id}/channels`
