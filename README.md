<p align="center">
  <a href="https://github.com/datarobot-community/datarobot-agent-application">
    <img src="./.github/datarobot_logo.avif" width="600px" alt="DataRobot Logo"/>
  </a>
</p>
<p align="center">
    <span style="font-size: 1.5em; font-weight: bold; display: block;">Agentic Starter application template</span>
</p>

<p align="center">
  <a href="https://datarobot.com">Homepage</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html">Documentation</a>
  ·
  <a href="https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html">Support</a>
</p>

<p align="center">
  <a href="https://app.datarobot.com/usecases/application-templates/69090966c601dbd8c8514516?referrerUrl=github">
    <img src="https://img.shields.io/badge/US-Open%20in%20a%20Codespace-%23909BF5?style=flat&labelColor=%2330373D" alt="US - Open in a Codespace">
  </a>
  <a href="https://app.eu.datarobot.com/usecases/application-templates/69090966c601dbd8c8514516?referrerUrl=github">
    <img src="https://img.shields.io/badge/EU-Open%20in%20a%20Codespace-%232BC46F?labelColor=%2330373D" alt="EU - Open in a Codespace">
  </a>
  <a href="https://app.jp.datarobot.com/usecases/application-templates/69090966c601dbd8c8514516?referrerUrl=github">
    <img src="https://img.shields.io/badge/JP-Open%20in%20a%20Codespace-%23EDA769?labelColor=%2330373D" alt="JP - Open in a Codespace">
  </a>
  <a href="https://app.jp.datarobot.com/usecases/application-templates/69090966c601dbd8c8514516?referrerUrl=github">
    <img src="https://img.shields.io/badge/JP-%E3%80%8CCodespace%20%E3%81%A7%E9%96%8B%E3%81%8F%E3%80%8D-%23EDA769?labelColor=%2330373D" alt="JP - 「Codespaceで開く」">
  </a>
  <a href="https://github.com/datarobot-community/datarobot-agent-application/tags">
    <img src="https://img.shields.io/github/v/tag/datarobot-community/datarobot-agent-application?label=version" alt="Latest Release">
  </a>
  <a href="/LICENSE">
    <img src="https://img.shields.io/github/license/datarobot-community/datarobot-agent-application" alt="License">
  </a>
</p>

This is a **soul-driven agentic application template** built on DataRobot. The agent's persona, capabilities, and tool access are defined entirely by **soul files** — swappable Markdown + JSON configs that live in `souls/` and require no code changes or restarts to swap. The DataRobot platform uses this template to scaffold personalized agent branches for users: when a user selects a domain pack and finalizes their soul configuration in the DR UI, a ready-to-develop branch is automatically created in this repo.

The stack: LangGraph agent · FastAPI backend · React/Vite frontend · MCP server — all deployable to DataRobot with one command.

> [!CAUTION]
> This repository updates frequently. Pull regularly to get the latest changes.

# Table of contents

- [Quick start](#quick-start)
- [Develop your agent](#develop-your-agent)
- [Soul system](#soul-system)
- [Deploy your agent](#deploy-your-agent)
- [MCP server](#mcp-server)
- [OAuth applications](#oauth-applications)
- [Agent-to-agent](#agent-to-agent)
- [Troubleshooting](#troubleshooting)
  - [Ports reference](#ports-reference)
- [Get help](#get-help)

For information on the latest changes, see the [CHANGELOG](CHANGELOG.md).

# Quick start

> [!CAUTION]
> macOS and Linux only. On Windows use a [DataRobot codespace](https://docs.datarobot.com/en/docs/workbench/wb-notebook/codespaces/index.html), [WSL](https://learn.microsoft.com/en-us/windows/wsl/install), or a [dev container](https://containers.dev/).

**Prerequisites** (install system-wide):

| Tool | Version | Install |
|------|---------|---------|
| `dr` (DataRobot CLI) | >= 0.2.55 | `curl https://cli.datarobot.com/install \| sh` · macOS: `brew install datarobot-oss/taps/dr-cli` |
| `git` | >= 2.30.0 | [git-scm.com](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) |
| `uv` | >= 0.9.0 | [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| `pulumi` | >= 3.163.0 | [pulumi.com](https://www.pulumi.com/docs/iac/download-install/) · no account needed: `pulumi login --local` |
| `task` | >= 3.43.3 | [taskfile.dev](https://taskfile.dev/docs/installation) |
| `node` | >= 24 | [nodejs.org](https://nodejs.org/en/download/) |

> [!NOTE]
> After installing `uv`, run `uv tool update-shell` once. You also need a C++ compiler and build tools to compile some Python packages.

**Set up and run:**

```sh
dr start      # first-time wizard: authenticates to DataRobot, creates .env, installs deps
dr run dev    # starts agent + backend + frontend + MCP server in parallel
```

Open [http://localhost:5173](http://localhost:5173). To run services individually: `dr run agent:dev`, `dr run fastapi_server:dev`, etc.

> [!NOTE]
> To update env vars: `dr dotenv edit`. To update after pulling changes: `dr component update`. If using a DataRobot codespace, expose ports 8080, 5173, 8842, and 9000 in your Session Environment tab.

# Develop your agent

The agent lives in `agent/agent/myagent.py` (`MyAgent`). It is **soul-driven** — the active soul's `SOUL.md` becomes the system prompt and `mcp-tools.json` controls which tools are available. To change agent behavior, edit the soul rather than the agent code. See the [Soul system](#soul-system) section below.

For deeper customization — adding custom tools, changing the LangGraph workflow, or modifying the frontend — see [AGENTS.md](AGENTS.md) and the DataRobot docs:

- [Customize your agent](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-development.html)
- [Add tools](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tools-integrate.html) · [Configure LLM providers](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-llm-providers.html) · [Add Python packages](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-python-packages.html)

# Soul system

The agent's behavior is driven by **souls** — swappable domain configurations that live in `souls/` at the repo root. Each soul defines two things:

| File | Purpose |
|------|---------|
| `SOUL.md` | Full system prompt: persona, capabilities, routing rules, domain context, output format |
| `mcp-tools.json` | Allowlist of MCP tool names the agent is permitted to use |

The active soul is tracked in `souls/.active` (a single-line file with the soul name). The agent re-reads both files on **every request** — no restart required.

## Directory layout

```
souls/
  .active                   ← active soul name (e.g. "supply-chain")
  supply-chain/
    SOUL.md
    mcp-tools.json
  data-analyst/
    SOUL.md
    mcp-tools.json
  __template__/             ← scaffold reference (not exposed as a soul)
    SOUL.md
    mcp-tools.json
```

## Switch the active soul

```sh
# Via API (no restart needed — takes effect on next agent request)
curl -X POST http://localhost:8081/api/v1/soul/swap/data-analyst

# Or directly
echo "data-analyst" > souls/.active
```

## Add a new soul

1. Copy `souls/__template__/` to `souls/<your-soul-name>/`
2. Edit `SOUL.md` — fill in the persona, capabilities, routing rules, domain context, and output format
3. Edit `mcp-tools.json` — list the MCP tool names the agent should have access to
4. Switch to it: `echo "<your-soul-name>" > souls/.active`

## Soul API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/soul/active` | Current soul name, available souls, active tool list |
| `POST` | `/api/v1/soul/swap/{name}` | Switch active soul (hot-swap, no restart) |
| `GET` | `/api/v1/soul/templates` | All built-in domain packs with full content and tools |
| `GET` | `/api/v1/soul/templates/{name}` | Single domain pack — for prefilling an editor |
| `POST` | `/api/v1/soul/scaffold-branch` | Create a new Git branch pre-loaded with a soul config |

## Scaffold branch (DR platform integration)

The `POST /api/v1/soul/scaffold-branch` endpoint is designed for the DataRobot platform. When a user selects a domain pack and finalizes their soul configuration in the DR UI, DR calls this endpoint. The backend creates a new Git branch with the soul files committed, and returns a clone URL the user can take and develop from locally.

**Required environment variables:**

```sh
GITHUB_TOKEN="ghp_..."     # GitHub PAT with `repo` scope
GITHUB_REPO="owner/repo"   # e.g. "datarobot-community/datarobot-agent-application"
SCAFFOLD_API_KEY="..."     # shared secret — DR sends as: Authorization: Bearer <value>
```

**Example request:**

```sh
curl -X POST http://localhost:8081/api/v1/soul/scaffold-branch \
  -H "Authorization: Bearer <SCAFFOLD_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "soul_name": "fraud-detection",
    "soul_content": "# Fraud Detection\n...",
    "tools": ["list_deployments", "predict_realtime", "tavily_search"],
    "base_branch": "main"
  }'
```

**Response:**

```json
{
  "branch_name": "soul/fraud-detection",
  "branch_url": "https://github.com/org/repo/tree/soul/fraud-detection",
  "clone_instructions": "git clone -b soul/fraud-detection https://github.com/org/repo.git"
}
```

The branch contains `souls/fraud-detection/SOUL.md`, `souls/fraud-detection/mcp-tools.json`, and `souls/.active` pointing to `fraud-detection` — ready to clone and run with `dr run dev`.

# Deploy your agent

```sh
dr run deploy
```

Deploys the agent, backend, frontend, and MCP server to DataRobot via Pulumi. Requires `pulumi login` (or `pulumi login --local`). The deployment output includes the live application URL, agent deployment ID, and MCP server endpoint.

> [!NOTE]
> First-time deployment takes several minutes. To tear down: `dr task run infra:down-yes`.

# MCP server

The Model Context Protocol (MCP) server exposes DataRobot platform capabilities as tools the agent can call. For configuration and available tool integrations, see [MCP server documentation](docs/mcp-server.md).

The active soul's `mcp-tools.json` controls which of the MCP server's tools the agent is allowed to use — giving each domain pack a scoped, purpose-built tool surface.

# OAuth applications

For detailed information about configuring OAuth applications, see [OAuth applications documentation](docs/oauth-applications.md).

# Agent-to-agent

Template agents can expose themselves as agent-to-agent (A2A) servers and connect to remote agents via the agent-to-agent protocol.

To expose an agent via A2A:

- Templates must have a `general.front_end.a2a` configuration block. By default, templates already include this.
- Run the agent with the experimental dragent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

To connect an agent via A2A to a remote agent:

- Uncomment the `function_groups` and `workflow.tool_names` blocks in the `workflow.yaml` file.
- Run the agent with the experimental dragent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

Enable the **ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS** feature flag in DataRobot to use environment variables in the `workflow.yaml` files.

### Agent cards and DataRobot deployments

When the `ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT` feature flag is enabled and you deploy an agent that exposes A2A server endpoints, the agent card for that agent is stored in DataRobot during deployment. Use the following endpoints:

- **List deployments with agent cards:** `GET deployments/?isA2AAgent=true`
- **Retrieve an agent card:** `GET deployments/<deployment_id>/agentCard`

### A2A agents hosted outside of DataRobot

For A2A agents hosted outside of DataRobot:

1. Create an external model with the "Agentic Workflow" target type and the default configuration.
2. Deploy the external model.
3. Push the agent card via `PUT deployments/<deployment_id>/agentCard`.

For external deployments, you can also remove the agent card with `DELETE deployments/<deployment_id>/agentCard`.

```python
deployments = dr.Deployment.list(filters=DeploymentListFilters(is_a2a_agent=True))
agent_card = deployment.get_agent_card()
# Only available for external deployments
deployment.upload_agent_card(agent_card)
deployment.delete_agent_card()
```

# Troubleshooting

## Ports reference

| Port | Component | Configurable |
|------|-----------|--------------|
| 8080 | Web application (proxied frontend) | No |
| 5173 | Vite dev server | No |
| 8842 | Agent endpoint | Yes — set during `dr start` wizard |
| 9000 | MCP server | Yes — `MCP_SERVER_PORT` in `.env` |

If using a DataRobot codespace, expose these ports in the **Exposed Ports** section of your **Session Environment** tab.

## Common issues

**`dr: command not found`** — CLI not on PATH. Run `which dr`; if missing, add its install directory to PATH or reinstall with `curl https://cli.datarobot.com/install | sh`.

**CLI version too old** — Run `dr self update`.

**Port already in use** — Find and kill: `lsof -i :<PORT> | grep LISTEN | awk '{print $2}' | xargs kill -9`. Or change the port in `.env`.

**Services won't start** — Verify all prerequisites are installed (`dr --version`, `uv --version`, etc.), run `dr run install`, and check that `.env` exists with required variables set.

**`dr start` wizard fails** — Re-run `dr start`. If `.env` is corrupt: `cp .env .env.backup && rm .env && dr start`.

**Agent can't connect to MCP server** — Check MCP server logs (`dr run mcp_server:dev`), verify `MCP_SERVER_PORT` matches in `.env`, and confirm `DATAROBOT_API_TOKEN` is set.

**`dr run deploy` fails** — Run `pulumi whoami` to check login status. Use `pulumi login --local` if no account. Review Pulumi output for the specific error.

**Frontend build fails** — Clear cache: `cd frontend_web && rm -rf node_modules dist && npm install`. Verify Node >= 24.

# Get help

- [DataRobot agentic AI documentation](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/index.html)
- [DataRobot CLI docs](https://github.com/datarobot-oss/cli) — run `dr --help` for quick reference
- [Contact DataRobot support](https://docs.datarobot.com/en/docs/get-started/troubleshooting/general-help.html)
- [Open a GitHub issue](https://github.com/datarobot-community/datarobot-agent-application)
