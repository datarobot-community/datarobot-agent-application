---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# Soul Factory

**Launch, manage, and govern AI agents — without building the infrastructure.**

Soul Factory is a native DataRobot app that gives every person in your org a front door to the dr-claw agent runtime. Business users get a one-click agent catalog. Developers get a forkable runtime. Admins get full fleet governance.

[Get started →](getting-started/quickstart.md){ .md-button .md-button--primary }
[Core Concepts](getting-started/core-concepts.md){ .md-button }
[App Flow](build/app-flow.md){ .md-button }

</div>

---

## Core Concepts

| Concept | Description |
|---|---|
| **Soul** | The agent's identity — a `SOUL.md` the runtime reads on every request, hot-swappable with zero downtime |
| **Pack** | Role-based agent template — pre-configured soul + tools for a specific job |
| **Domain** | Active soul loaded via `souls/.active` — set per-agent, switchable live |
| **Session** | A running agent instance — chat history, SSE log stream, tool calls, HITL events |
| **HITL** | Human-in-the-loop gate — write operations held for admin approval before execution |
| **OpenShell** | Envoy-based tool firewall — every MCP call is allowed, blocked, or queued and logged |

[Full definitions →](getting-started/core-concepts.md){ .md-button }

---

## How It Works

<div class="sf-steps-inline" markdown>

**1. Browse packs** — pick a domain pack (core, data, dev, mlops). Each surfaces a pre-configured soul + tool set.

**2. Configure** — Name your agent, set HITL rules, pick allowed models. Four fields. Under 2 minutes.

**3. Launch** — Soul Factory creates the DR Workload, wires LLM Gateway and Global MCP, runs a health check. Live.

**4. Interact** — Chat via Web UI. The agent executes MCP tools, streams tokens via SSE, and queues write operations for HITL review.

**5. Govern** — Admins see the full fleet — spend, error rates, HITL backlog, and log streams — in one surface.

</div>

---

## Soul Factory vs. raw DR Workloads

| | **Soul Factory** | **DR Workloads (raw)** |
|---|---|---|
| Who it's for | Business users, devs, admins | ML engineers |
| Agent config | SOUL.md + domain packs | Custom code |
| Tool governance | Global MCP + OpenShell + HITL | DIY |
| Launch experience | Catalog → Configure → Live &lt;2 min | API + infra setup |
| Fleet visibility | Fleet, Logs, Cost & Usage pages | None built-in |
| Skill marketplace | Submit → pipeline → Global MCP | None |

---

## What's Built

All 12 pages shipped in Cycle 1 (April 2026 — 5 days).

| Page | Status |
|---|---|
| Agent Catalog | ✅ Live |
| Configure Wizard | ✅ Live |
| My Agents | ⚠ Mock data (Cycle 2) |
| Agent Detail: Overview | ✅ Live |
| Agent Detail: Chat | ✅ Live SSE |
| Agent Detail: Skills | ✅ Live MCP + fallback |
| Agent Detail: Logs | ⚠ Simulated stream |
| Agent Detail: Cost | ⚠ Mock data |
| Fleet | ⚠ Mock data |
| Logs (global) | ⚠ Simulated stream |
| HITL Queue | ✅ Approve / Reject live |
| Integration Governance | ✅ UI done |

[See Cycle 2 roadmap →](reference/cycle-2.md){ .md-button }
