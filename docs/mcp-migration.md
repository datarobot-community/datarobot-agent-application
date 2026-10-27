# Move your MCP server out of the Agentic Starter

> [!IMPORTANT]
> **This is a breaking change.** The Agentic Starter no longer includes an MCP server (`mcp_server/`).
> If your app had one, your agent loses its MCP tools when you update, and your next deploy stops until you act.

## What changed

- **The template:** the MCP server that older versions bundled in `mcp_server/` is gone. For the built-in DataRobot tools, use the [DataRobot Global MCP](#built-in-tools-use-the-datarobot-global-mcp), which DataRobot runs for you. For your own tools, run a standalone MCP server built from the [DataRobot MCP template](https://github.com/datarobot-community/datarobot-mcp-template). The agent still uses MCP tools: it connects to the server you set in `.env`.
- **When you pull this version:** git deletes `mcp_server/` and its infra. If you changed those files, `git pull` stops with conflicts ([see below](#troubleshooting)). Files git doesn't track stay in `mcp_server/`: files you added, and what the old server's install created (its `.venv`). Delete the folder once you have what you need from it. Everything you had is still in git history.
- **Locally:** from then on, `dr run dev` runs the agent without the old server's tools.
- **Your next deploy:** if your app is deployed, its old MCP server is still in DataRobot, and deploying this version would delete it. So every deploy stops, before anything changes, until you confirm:

  ```text
  MCP migration: deploy stopped. Nothing changed.

  This version of the template no longer includes the MCP server (the
  mcp_server/ folder): MCP servers now run as standalone apps. Your deployed app
  still has the old one:
    - MCP Server [mcp_server] Session Secret Key
    - [my-agent-app] [mcp_server] Custom Model
    - [my-agent-app] [mcp_server] Deployment
    - [my-agent-app] [mcp_server] Prediction Environment
    - [my-agent-app] [mcp_server] Registered Model
  This deploy would delete it, with its settings and credentials, and your agent
  would lose its MCP tools.
  ...
  ```

  Apps that were never deployed, and new apps, don't see this.

## What to do

1. **Decide where your MCP tools go:**
   - **The tools that came with the bundled server** (the tool sets you switched on in `.env`): point your agent at the [DataRobot Global MCP](#built-in-tools-use-the-datarobot-global-mcp), if it has them. There is no server to build or deploy.
   - **Your own tools**, and built-in tools the Global MCP doesn't have: move them to a standalone MCP server ([steps below](#move-your-tools-to-a-standalone-mcp-server)), and set `MCP_DEPLOYMENT_ID` in `.env`.
   - **Or decide that you don't need them.** For example, you never changed the bundled server and never switched on its tools.
2. **Confirm.** Add this line to `.env`:

   ```sh
   MCP_MIGRATION_CONFIRMED=1
   ```

   In CI, set it in the pipeline's environment for the deploy.
3. **Deploy once:** `dr run deploy`. Its preview lists the old server's resources it deletes, under `MCP migration: MCP_MIGRATION_CONFIRMED is set`. The deploy deletes them from DataRobot, and deploys your agent with the MCP server set in `.env`, if any. Later deploys say that you can remove the line in step 2.

`dr start` and `task deploy-dev` update only part of your app, so they can't delete the old server: run `dr run deploy` once first.

To keep the bundled server instead, see [Keep the MCP server in this app](#keep-the-mcp-server-in-this-app).

> [!NOTE]
> The check that stops the deploy is `infra/infra/mcp_migration_check.py`. It reads your Pulumi stack, and stops only while the stack still has the old server (resources named `[mcp_server] ...`) and `MCP_MIGRATION_CONFIRMED` isn't set. It covers every way of deploying: `dr run deploy`, `dr start`, `dr run infra:up-yes`, `task infra:up` and `pulumi up`. It never changes your files.

## Built-in tools: use the DataRobot Global MCP

If you only used the tools that came with the bundled server, you may not need an MCP server of your own. The DataRobot Global MCP is an MCP server that DataRobot runs on your instance, at a fixed address, with nothing to deploy or maintain. Which tools it has depends on your DataRobot version and settings: see [MCP server overview](https://docs.datarobot.com/en/docs/agentic-ai/agentic-mcp/agentic-mcp-overview.html) in the DataRobot docs.

Which tools you used depends on what `MCP_CLI_CONFIGS` (or the `ENABLE_*_TOOLS` settings) switched on in your `.env`:

| You switched on | Use |
|---|---|
| Tool sets, such as `predictive`, `jira`, `confluence`, `gdrive`, `microsoft_graph`, `perplexity` or `tavily` | The DataRobot Global MCP, for the tools it has. For the others, a [standalone MCP server](#move-your-tools-to-a-standalone-mcp-server) with the same `MCP_CLI_CONFIGS`. |
| Nothing | No MCP server: the bundled server had no tool sets switched on by default. Projects created from version 11.4.6 or earlier are the exception: their server had the Google Drive tools (`gdrive`) on. |

To point your agent at the Global MCP, set these two lines in `.env`:

```sh
# The DataRobot Global MCP: your DATAROBOT_ENDPOINT followed by /genai/globalmcp/mcp
EXTERNAL_MCP_URL=https://app.datarobot.com/api/v2/genai/globalmcp/mcp
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <your DataRobot API key>"}'
```

- **The address** is your DataRobot endpoint followed by `/genai/globalmcp/mcp`. For example, with `DATAROBOT_ENDPOINT=https://app.eu.datarobot.com/api/v2`, it is `https://app.eu.datarobot.com/api/v2/genai/globalmcp/mcp`.
- **The API key** goes in `EXTERNAL_MCP_HEADERS`, because the agent doesn't send its DataRobot credentials to an `EXTERNAL_MCP_URL`. `dr run deploy` passes both settings to the deployed agent as runtime parameters, so the key is stored with the deployment: use a key meant for it.
- **Remove `MCP_DEPLOYMENT_ID` and `MCP_WORKLOAD_ID`** from `.env`, if they're set: they take precedence over `EXTERNAL_MCP_URL`. A leftover `MCP_SERVER_PORT` is ignored, and can go too.

Run `dr run dev`, and ask the agent which tools it has.

Without more settings, the agent gets every tool the Global MCP has. To give it only the tools it needs, list their names, separated by commas, in the `x-datarobot-mcp-tools` header:

```sh
EXTERNAL_MCP_HEADERS='{"Authorization": "Bearer <your DataRobot API key>", "x-datarobot-mcp-tools": "<tool name>,<tool name>"}'
```

The header's name starts with `x-`: the Global MCP ignores `datarobot-mcp-tools`. Then follow [What to do](#what-to-do) to confirm and deploy.

The Global MCP is available in recent DataRobot releases. If your instance doesn't have it, use a [standalone MCP server](#move-your-tools-to-a-standalone-mcp-server). See [MCP server overview](https://docs.datarobot.com/en/docs/agentic-ai/agentic-mcp/agentic-mcp-overview.html) in the DataRobot docs.

## Get your old MCP files from git

Every version of your MCP server is still in git. Find the commit that removed it, and read your files from the commit before it:

```sh
UPDATE=$(git log -1 --first-parent --diff-filter=D --format=%h -- mcp_server/app/main.py)
git show "$UPDATE^:mcp_server/app/tools/user_tools.py"     # one file
git checkout "$UPDATE^" -- mcp_server/app/tools/           # a folder, back into your project
```

This works whether the update came in as a merge or a squash. If you pulled with `git pull --rebase`, the rebase dropped your edits to deleted files: find the commit you were on before the pull with `git reflog`, and use it instead of `"$UPDATE^"`.

## Move your tools to a standalone MCP server

### 1. Create the server

1. Get the MCP template in its own folder, next to your Agentic Starter project:

   ```sh
   git clone https://github.com/datarobot-community/datarobot-mcp-template.git my-mcp-server
   cd my-mcp-server
   task install
   ```

2. Create `.env` from `.env.template`, and add:
   - `DATAROBOT_API_TOKEN`, `DATAROBOT_ENDPOINT`, and a `SESSION_SECRET_KEY`;
   - the MCP settings from your Agentic Starter `.env`, such as `MCP_CLI_CONFIGS` and the keys of the tools you switched on;
   - `MCP_SERVER_PORT=9000`. The template's default port, 8080, is taken by the Agentic Starter web app when you run both locally.

3. Copy **your** files from the old server ([from git](#get-your-old-mcp-files-from-git)). Server code in the template lives in `dr_mcp/`:

   | From the old server | To the MCP template |
   |---|---|
   | `mcp_server/app/tools/<your files>.py` | `dr_mcp/app/tools/` |
   | `mcp_server/app/prompts/<your files>.py` | `dr_mcp/app/prompts/` |
   | `mcp_server/app/resources/<your files>.py` | `dr_mcp/app/resources/` |
   | Your own packages under `mcp_server/app/` | `dr_mcp/app/`. Imports such as `app.tools...` stay the same. |
   | `mcp_server/app/core/*.py`, if you changed them | `dr_mcp/app/core/` |
   | Your tests under `mcp_server/app/tests/` | `dr_mcp/app/tests/` |
   | `infra/infra/mcp_server_user_params.py`, if it lists parameters | `infra/infra/dr_mcp_user_params.py`. Change its import to `infra.dr_mcp_infra.mcp_utils`. |

   The stock files are already in the template.

4. Add the Python packages your tools need: `cd dr_mcp && uv add <package> && cd ..`.
5. Run the server and try your tools: `task dev` serves `http://localhost:9000/mcp/`.

### 2. Deploy it

```sh
task deploy
cd infra && uv run pulumi stack output --json && cd ..
```

From the outputs, note `[<stack>] [dr_mcp] Deployment Id`.

### 3. Point your agent at it

In the Agentic Starter `.env`, set **one** of these:

```sh
# MCP server deployed in DataRobot. DataRobot credentials are forwarded.
MCP_DEPLOYMENT_ID=<Deployment Id>

# MCP server deployed to the Workload API. DataRobot credentials are forwarded.
#MCP_WORKLOAD_ID=<Workload Id>

# Any other MCP endpoint. DataRobot credentials are NOT forwarded.
#EXTERNAL_MCP_URL=https://example.com/mcp/
```

Run `dr run dev`, and ask the agent which tools it has. Then follow [What to do](#what-to-do) to confirm and deploy.

If anything else used the old MCP endpoint (`.../deployments/<old id>/directAccess/mcp`), such as Cursor, VS Code, Claude Desktop, other agents or scripts, point it at the new server: the old endpoint stops working after that deploy.

For Okta cross-application access (XAA), see [MCP servers that require Okta XAA](agent/mcp.md#mcp-servers-that-require-okta-xaa).

## Keep the MCP server in this app

> [!IMPORTANT]
> **We recommend moving your tools to a standalone MCP server instead.**
> The standalone [DataRobot MCP template](https://github.com/datarobot-community/datarobot-mcp-template) keeps getting updates. A server kept in this app doesn't: template updates don't include it, new versions of the Agentic Starter aren't tested with it, and you update it yourself.

1. Add the MCP component back:

   ```sh
   dr component add https://github.com/datarobot-community/af-component-datarobot-mcp.git
   ```

2. Copy your own files back into `mcp_server/` ([from git](#get-your-old-mcp-files-from-git)).
3. Add the server to `.taskfile-data.yaml`, so that `dr run dev` starts it:

   ```yaml
     - name: mcp_server
       port: 9000
   ```

With the default name `mcp_server`, deploys include the server again and connect the agent to it, so the deploy doesn't stop. To update the server later: `uvx copier update -a .datarobot/answers/drmcp-mcp_server.yml --trust`.

## Troubleshooting

| What you see | What to do |
|---|---|
| `git pull` stops with `CONFLICT (modify/delete): mcp_server/...` | You changed files this update deletes. For each one, keep the deletion (`git rm <file>`), then run `git commit --no-edit`. Your versions stay in git history ([get them back](#get-your-old-mcp-files-from-git)). |
| `git pull` says `Your local changes to the following files would be overwritten by merge` | Git changed nothing. Commit your changes, then pull again. |
| `git stash pop` reports a conflict in an MCP file | Your edits are still in the stash (`git stash show -p`). Keep the deletion, or [keep the server](#keep-the-mcp-server-in-this-app) and pop the stash again. |
| After the pull, `git status` still shows `mcp_server/`, or `dr component update` says `Destination repository is dirty` | Git deleted only the files it tracked. What's left are files it didn't track: the old server's `.venv`, the tool lists its install generated (`mcp_server/dev_tools/`), and any files you added. Once you have what you need from it, delete the folder: `rm -rf mcp_server`. |
| `MCP migration: deploy stopped. Nothing changed.` | Follow [What to do](#what-to-do). |
| After confirming, `dr start` still shows `MCP migration: MCP_MIGRATION_CONFIRMED is set`, and the old server is still in DataRobot | `dr start` and `task deploy-dev` update only part of your app: they leave the old server, and your deployed agent, as they are. Run `dr run deploy` once to delete the old server. |
| `ModuleNotFoundError` for `mcp_server_infra` or `mcp_utils` during a deploy | You kept an MCP infra file while resolving the pull, such as `infra/infra/mcp_server_user_params.py`. Delete it, and commit. |
| `dr run dev` waits for `mcp_server`, or `task: No Taskfile found at ".../mcp_server/Taskfile.yaml"` | You kept the old `.taskfile-data.yaml` entry or `Taskfile.yml` while resolving the pull. Remove the `mcp_server` entry from `.taskfile-data.yaml`, and run `dr task compose`. |
| The agent answers without tools, and the logs show `Failed to connect to MCP server ... Continuing without MCP tools` | `.env` doesn't point at a running MCP server. Set `MCP_DEPLOYMENT_ID`, `MCP_WORKLOAD_ID` or `EXTERNAL_MCP_URL`, and remove `MCP_SERVER_PORT` unless an MCP server listens on that port. See [MCP tools](agent/mcp.md). |
| You confirmed and deployed, and need the old tools back | Move them to a standalone server, or keep the server in this app, from [git](#get-your-old-mcp-files-from-git). The server gets a new deployment ID, so update other clients. |
