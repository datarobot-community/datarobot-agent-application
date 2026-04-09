# File Map

An annotated listing of every significant file in the `dr-claw` repository.

---

## Root

| File | Purpose |
|---|---|
| `README.md` | Project overview and quick-start |
| `.env.example` | Template for required environment variables |
| `requirements.txt` | Python backend dependencies |
| `pyproject.toml` | Python project config + linting rules |
| `docker-compose.yml` | Local dev stack (backend + Redis) |

---

## `app/` — FastAPI backend

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app factory, middleware, lifespan hooks |
| `app/routers/agents.py` | Agent CRUD + workload lifecycle endpoints |
| `app/routers/sessions.py` | Session create/read + SSE message stream |
| `app/routers/hitl.py` | HITL queue list + resolve endpoints |
| `app/routers/skills.py` | Skills library CRUD |
| `app/routers/events.py` | SSE event stream per agent |
| `app/services/soul.py` | SOUL.md load, parse, write to LRS |
| `app/services/session.py` | Session open/close, LRS writes |
| `app/services/hitl.py` | HITL trigger + resolution logic |
| `app/services/mcp_proxy.py` | Relay tool calls to Global MCP server |
| `app/services/llm_gateway.py` | DR LLM Gateway client + billing hooks |
| `app/models/` | Pydantic request/response schemas |

---

## `frontend/` — Vite + React

| File/Dir | Purpose |
|---|---|
| `frontend/src/pages/` | Route-level page components |
| `frontend/src/pages/MyAgents.tsx` | Agent card grid |
| `frontend/src/pages/AgentDetail.tsx` | Tabbed detail view |
| `frontend/src/pages/Chat.tsx` | Live SSE chat interface |
| `frontend/src/pages/Fleet.tsx` | Admin fleet table |
| `frontend/src/pages/HITLQueue.tsx` | Approval queue |
| `frontend/src/pages/Logs.tsx` | Aggregate log viewer |
| `frontend/src/pages/Cost.tsx` | Spend dashboard |
| `frontend/src/components/` | Shared components (AgentCard, LogLine, etc.) |
| `frontend/src/lib/api.ts` | Typed API client (fetch wrappers) |
| `frontend/src/lib/sse.ts` | SSE connection manager |
| `frontend/src/lib/store.ts` | Zustand global state |
| `frontend/src/lib/theme.ts` | DR design tokens |

---

## `souls/` — Soul definitions

| File | Purpose |
|---|---|
| `souls/nemoclaw/SOUL.md` | Default nemoclaw soul |
| `souls/templates/base.md` | Minimal soul template for new agents |
| `souls/templates/data-analyst.md` | Data analysis soul template |
| `souls/templates/code-review.md` | Code review soul template |

---

## `skills/` — Skill modules

| File | Purpose |
|---|---|
| `skills/web-search/` | Web search via DR MCP tool |
| `skills/dr-deployment-mgr/` | DR deployment create/update/delete |
| `skills/code-executor/` | Sandboxed Python execution |
| `skills/*/SKILL.md` | Skill description and examples |
| `skills/*/handler.py` | Skill execution logic |
| `skills/*/mcp-tools.json` | MCP tool manifest |

---

## `scripts/`

| File | Purpose |
|---|---|
| `scripts/gen_mcp_jwt.py` | Generate a short-lived MCP JWT |
| `scripts/seed_mock_data.py` | Populate dev DB with mock agents/sessions |
| `scripts/test_skill.py` | Interactive skill tester against a SOUL |

---

## `docs/`

| File/Dir | Purpose |
|---|---|
| `docs/` | MkDocs source (this documentation) |
| `mkdocs.yml` | MkDocs configuration |
| `docs/stylesheets/extra.css` | Custom CSS overrides |

---

## Configuration files

| File | Purpose |
|---|---|
| `dr-soul.md` | Dev setup notes (not deployed) |
| `grand_plan.md` | Product vision and user journeys |
| `PLAN.md` | Cycle 1 build history and decisions |
| `cycle-2.md` | Cycle 2 implementation spec |

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
