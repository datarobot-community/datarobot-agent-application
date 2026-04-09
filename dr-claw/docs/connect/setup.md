# Setup Guide

Two values wire Soul Factory to live data. Everything else works out of the box.

!!! tip "Just browsing?"
    Skip straight to the [Quickstart](../getting-started/quickstart.md) for a guided first run, or jump into the [Catalog](https://localhost) — mock data works without any config.

---

## Quick Start

```bash
workon datarobot-11.6
./start.sh
open https://localhost  # → Agents tab
```

---

## Step 1 — Workload ID

**File:** `client/js/agents/api/workload-config.js`

```js
export const WORKLOAD_ID = 'REPLACE_ME'; // ← paste workload ID here
export const CHAT_MODEL  = 'openclaw:agent'; // ← change if chat returns 404
```

Deploy nemoclaw as a DR Workload, copy the `id` from the response, paste it here.

**Unlocks:** Chat, Soul Editor, Tools tab, Status tab, Domain Pack switching.

All API calls route through the DR Predictions Gateway — no CORS or auth setup needed:

```
/api/v2/endpoints/workloads/{id}/v1/chat/completions
/api/v2/endpoints/workloads/{id}/admin/tools
/api/v2/endpoints/workloads/{id}/admin/config
/api/v2/endpoints/workloads/{id}/healthz
```

!!! tip "Chat returning 404?"
    Change `CHAT_MODEL` to match what nemoclaw expects — try `'default'`, `'nemoclaw'`, or `'gpt-4o'`.

---

## Step 2 — Global MCP JWT

**Script:** `dr-claw/patch-nginx.sh`

```bash
# Get a fresh JWT:
# staging.datarobot.com → DevTools Network → any /api-gw/ request → Authorization header

./dr-claw/patch-nginx.sh "eyJhbGciOiJ..."
supervisorctl restart nginx
```

**Unlocks:** Skills page (live Global MCP tools) + Configure wizard tool chips.

!!! warning "JWT expires every ~24 hours"
    Re-run the patch script when Skills shows "Could not connect."

**Long-term fix (Cycle 2):** Add a public MCP ingress route to `api_gateway/genai/api.py` so DR API tokens work instead of short-lived JWTs. See [MCP Proxy Migration](../reference/cycle-2.md#9-mcp-proxy-migration).

---

## Live vs. Mock Status

| Feature | Status | Requires |
|---------|--------|---------|
| Chat | ✅ Wired | `WORKLOAD_ID` |
| Soul Editor load + save | ✅ Wired | `WORKLOAD_ID` |
| Tools tab | ✅ Wired | `WORKLOAD_ID` |
| Status tab | ✅ Wired | `WORKLOAD_ID` |
| Domain pack switch | ✅ Wired | `WORKLOAD_ID` |
| Skills page tools | ✅ Live + 49-tool static fallback | MCP JWT |
| Configure tool chips | ✅ Live + static fallback | MCP JWT |
| Integration Governance | ✅ UI done | Mock data (real: Cycle 2) |
| Heartbeat / Channels | ✅ Mock UI | Real nemoclaw endpoints (Cycle 2) |
| My Agents list | ⚠️ Mock | `GET /api/v2/workloads` |
| Fleet table | ⚠️ Mock | `GET /api/v2/workloads` admin |
| Launching animation | ⚠️ Mock (setTimeout) | `POST /api/v2/workloads` + poll |
| Pause / Stop buttons | ⚠️ No-op | `POST/DELETE /api/v2/workloads/{id}` |
| Cron tab | ⚠️ Mock UI | nemoclaw `/admin/crons` |
| Cost & Usage | ⚠️ Mock chart | `GET /api/v2/llm-gateway/usage` |
| HITL queue | ⚠️ Mock | `GET /api/v2/hitl/queue` |
| HITL clarify + audit | ⚠️ Not built | `POST /hitl/{id}/clarify` + audit log |
| Logs stream | ⚠️ Mock (setInterval) | Real Envoy SSE |
| GitHub repo fork | ⚠️ Instructions only | GitHub OAuth + fork API |

---

## Central Config File Map

| What | Where |
|------|-------|
| Workload ID + chat model | `client/js/agents/api/workload-config.js` |
| MCP proxy URL | `client/js/agents/api/mcp-config.js` |
| Mock agents | `client/js/agents/mock-data/agents.js` |
| Mock packs | `client/js/agents/mock-data/packs.js` |
| nginx patch script | `dr-claw/patch-nginx.sh` |
| nginx template | `drplatform/templates/nginx/webserver.conf.j2inc` |
| dr-soul branch | `https://github.com/datarobot/dr-soul/tree/elvin/dr-claws` |
