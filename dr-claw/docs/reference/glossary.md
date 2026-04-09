# Glossary

All terms used in Soul Factory documentation, alphabetical.

---

**AGUI**
Agent GUI — the web-based chat interface embedded in Agent Detail. Serves as an alternative to the Slack bot interface.

**Autopilot**
DataRobot's automated model training pipeline. Accessible via the `start_autopilot` MCP tool.

**BLOCK event**
An OpenShell log event indicating a tool call was denied — either because the tool wasn't in the agent's `mcp-tools.json` allowlist, or because it was IP-filtered by Envoy. Not a failure — it's the security model working.

**CFDS**
Customer-Facing Data Science. The CFDS Agent pack is tailored for the CFDS team's workflow — meeting prep, model insights, and customer-facing materials.

**Chat model alias**
The `CHAT_MODEL` constant in `workload-config.js`. Tells nemoclaw which model identifier to use for the `/chat/completions` endpoint. Default: `openclaw:agent`.

**Deep-Coder pack**
The developer-focused pack. Uniquely supports multi-agent sessions (multiple parallel conversations). Has access to `create_skill`, `validate_skill`, and `search_service_api`.

**Domain**
The active soul configuration. Switching domains hot-swaps `SOUL.md` without restarting the agent container.

**Domain Pack**
See **Pack**.

**Envoy**
The proxy layer (OpenShell) that intercepts all tool calls. Emits structured SSE events for every tool interaction.

**Fleet**
Admin view of all running agents across the org — owner, pack, token usage, anomaly flags.

**Global MCP**
The shared Model Context Protocol server that hosts all approved tools and skills.
Base URL: `https://beta-global-mcp.stg.ue1.aws.int.datarobot.com/mcp`

**HITL**
Human-in-the-loop. A governance mechanism that holds agent write operations in a queue for admin review before execution. Every decision is logged to the audit trail.

**LRS**
Likely "LRS endpoint" — the DR staging endpoint for workload management. Used for `POST /api/v2/workloads` and related calls.

**MCP**
Model Context Protocol. The standard for connecting AI agents to tools and resources. Soul Factory uses Anthropic's MCP spec.

**MCP JWT**
Short-lived OAuth token required to authenticate against the Global MCP server. Obtained from DevTools → any `/api-gw/` request → Authorization header. Valid for ~24 hours.

**mcp-tools.json**
The tool allowlist for an agent. OpenShell enforces it — any tool not in this file triggers a `BLOCK` event.

**nemoclaw**
The agent runtime container. Runs one instance per deployed agent. Reads `SOUL.md` and `mcp-tools.json` on every request. Exposes `/admin/config`, `/admin/tools`, `/healthz`, and the chat completion endpoint.

**NullClaw**
Local development runtime for nemoclaw. Run with `task dev`. Boots in under 200ms.

**OpenShell**
The Envoy-based proxy that intercepts every tool call between the agent and Global MCP. Enforces the `mcp-tools.json` allowlist and emits `ALLOW`, `BLOCK`, `LLM`, `HITL`, and `CRON` events.

**Pack**
A pre-built agent template for a specific role. Bundles a `SOUL.md` persona, a default tool set, and a killer use case shown on the catalog card.

**Session**
A running agent instance — chat history, SSE log stream, tool calls, HITL events. Switching agents in the UI remounts the component to prevent session state bleed.

**SKILL.md**
The human-readable spec for a community-built integration. Defines what the skill does, what tools it provides, auth requirements, and usage examples. Required for the Skills pipeline.

**Soul / SOUL.md**
The agent's system prompt, structured into six sections: Identity, Capabilities, Domain Context, Tool Usage, Output Format, Routing. Re-read by the runtime on every request.

**Soul Editor**
The in-app editor in Agent Detail that loads the live `soul_md` from `/admin/config` and allows saving changes directly to the running agent.

**Soul Factory**
The full product — the DataRobot Custom App (Soul Factory UI, or "dr-claw") plus the nemoclaw runtime and Global MCP infrastructure.

**SSE**
Server-Sent Events. The streaming protocol used for chat responses and log streams. All log events and chat completions stream via SSE.

**Workload**
A DR deployment unit. One nemoclaw instance = one workload. Managed via `POST/GET/DELETE /api/v2/workloads`.

**WORKLOAD_ID**
The deployment ID of a running nemoclaw workload. Set in `workload-config.js`. Unlocks live chat, soul editing, tools, and status features.
