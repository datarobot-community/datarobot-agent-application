# Changelog

---

## Cycle 1 — April 2026

**5-day Grand Challenge build.** All 12 pages shipped and navigable.

### What shipped

#### Pages
All 12 pages built and navigable with full routing, DR design system integration, and mock data where live APIs are pending.

| Page | Highlight |
|------|-----------|
| Catalog | Pack grid with search filter, real MCP tool names in pack skills |
| Configure | 49 MCP tools in selector, pre-seeded from pack defaults, Select all / Clear |
| Launching | 5-step auto-animation, mint live state, navigates to My Agents with pre-selected agent |
| Get the Repo | Generates agent-specific SOUL.md + mcp-tools.json, points to real dr-soul branch |
| My Agents | Agent tabs at top (Option D) — horizontal tab bar, `key={agent.id}` isolation |
| Agent Detail | 9-tab layout with live chat, soul editor, domain packs, tools, cron, memory, status, heartbeat, channels |
| Skills | 49 live MCP tools via proxy, amber "MCP offline" banner + static fallback |
| Fleet | Sticky header + expandable anomaly panel (Option C) |
| Logs | BLOCK/ALLOW/LLM/CRON badges, simulated SSE stream |
| HITL Queue | Approve / Reject wired |
| Cost & Usage | 7-day SVG bar chart + cost-by-pack table |
| Integration Governance | Health cards, approve/reject pending integrations |

#### Agent Detail Tabs

| Tab | Notes |
|-----|-------|
| Chat | SSE streaming, compact dropdown selector, per-agent sessions, multi-agent for Deep-Coder only |
| Soul Editor | Fetches live `soul_md` from `/admin/config`, Save to Agent + Download SOUL.md |
| Domain Packs | Activate POSTs to `/admin/config`, tool chips per pack |
| Tools & Skills | MCP tools, sub-tabs |
| Cron Jobs | Toggle, run now, last-run output |
| Memory | Knowledge cards, search |
| Status | Health dots, config table |
| Heartbeat | Mock UI — pulse chart + ping history |
| Channels | Mock UI — Slack, webhook, email channels |

#### Infrastructure
- nginx patch script (`dr-claw/patch-nginx.sh`) for MCP JWT injection
- `workload-config.js` as single source of truth for all endpoint derivation
- `mcp-client.js` — full MCP handshake + SSE parse
- React Query hooks for all API calls
- SSE streaming chat via native `fetch` (no axios — doesn't handle event streams)

#### Technical decisions
- No new npm dependencies added
- DR `IconSidebar` component (same as Registry) — not a custom nav
- `key={agent.id}` on `AgentDetailPanel` forces remount on agent switch — prevents chat/soul state bleed
- `heading-03` typography spec: `1.5rem / weight 500 / letter-spacing -0.025rem`
- `var(--uxr-area-content-margin-y/x)` for content padding

---

### What's wired live

| Feature | Requires |
|---------|---------|
| Chat (SSE streaming) | `WORKLOAD_ID` |
| Soul Editor — load + save | `WORKLOAD_ID` |
| Tools tab | `WORKLOAD_ID` |
| Status tab | `WORKLOAD_ID` |
| Domain pack switch | `WORKLOAD_ID` |
| Skills page (49 live MCP tools) | MCP JWT |
| Configure tool selector | MCP JWT |

---

### What's mock (Cycle 2)

| Feature | What it needs |
|---------|--------------|
| My Agents list | `GET /api/v2/workloads?owner=me` |
| Fleet table | `GET /api/v2/workloads` admin scope |
| Launching animation | `POST /api/v2/workloads` + poll `/status` |
| Log stream | Real Envoy SSE |
| HITL clarify + audit | `POST /hitl/{id}/clarify` + audit log |
| Cost & Usage | `GET /api/v2/llm-gateway/usage` |
| Pause / Stop buttons | `POST/DELETE /api/v2/workloads/{id}` |
| GitHub repo fork | GitHub OAuth + fork API |

---

### Known gaps (deferred)

- `packs.js` missing `defaultRole` — Configure role field starts blank
- Chat tab empty state copy is generic
- Log filters exist in UI but don't filter the stream yet
- Anomaly click-through navigates to Agent Detail but doesn't scroll to the anomaly event
- Skills submit pipeline is simulated (timer), not wired to real MCP `create_skill`

---

## Cycle 2 — Upcoming

See [Cycle 2 Roadmap](cycle-2.md) for the full plan and priority order.
