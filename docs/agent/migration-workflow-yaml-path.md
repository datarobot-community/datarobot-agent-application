# `workflow.yaml` path migration (11.9.3)

This guide covers the breaking layout change introduced in agent component **11.9.3** ([af-component-agent](https://github.com/datarobot-community/af-component-agent); adopted in this recipe by [BUZZOK-30290 / BUZZOK-30810](https://github.com/datarobot-community/recipe-datarobot-agent-application/pull/586), commit `018bff4`).

## Summary

`workflow.yaml` moved out of the inner Python package to the **agent component root**:

| | Path (from repository root) |
|---|---|
| **Before** | `agent/agent/workflow.yaml` |
| **After** | `agent/workflow.yaml` |

`workflow.yaml` is the top-level NeMo Agent Toolkit (NAT) configuration for an agent. It is **not** only a DRAgent concern.

| Front server | How `workflow.yaml` is used |
|---|---|
| **DRAgent** (`ENABLE_DRAGENT_SERVER=true`) | NAT loads `workflow.yaml` to build the FastAPI front server, tools, LLMs, middleware, and workflow graph. |
| **DRUM** (default) | **NAT framework agents** (`NatAgent` / `per_user_tool_calling_agent`) load `workflow.yaml` through `workflow_path` in `myagent.py` to orchestrate the agent. LangGraph, CrewAI, LlamaIndex, and Base agents use framework code in `myagent.py` on DRUM; `workflow.yaml` is still generated for DRAgent and shared infrastructure (for example, moderation and memory wrappers when enabled). |

If you upgrade a project that still has `agent/agent/workflow.yaml`, DRUM deployments of NAT agents and DRAgent local runs can fail to find the workflow file unless you relocate it and update `workflow_path`.

## Migration steps

### 1. Move the file

```sh
git mv agent/agent/workflow.yaml agent/workflow.yaml
```

Remove any leftover copy under `agent/agent/` so only one `workflow.yaml` exists.

### 2. Update `workflow_path` in NAT `myagent.py`

**Before** (file co-located with `myagent.py`):

```python
workflow_path: Path = Path(__file__).parent / "workflow.yaml",
```

**After** (`workflow.yaml` one directory up):

```python
workflow_path: Path = Path(__file__).parent.parent / "workflow.yaml",
```

### 3. Update Taskfile and CLI references

Generated `agent/Taskfile.yml` now passes `workflow.yaml` (relative to the `agent/` working directory), not `agent/workflow.yaml`. If you customized paths, align them:

```yaml
# DRAgent dev server
nat dragent serve --config_file workflow.yaml ...

# CLI default
export DRAGENT_CONFIG_FILE="${DRAGENT_CONFIG_FILE:-workflow.yaml}"
```

### 4. Search for stale paths

Check custom scripts, tests, and infrastructure for the old location:

```sh
rg 'agent/agent/workflow\.yaml' .
```

Infrastructure in this template resolves the file with a primary/fallback lookup (`agent/workflow.yaml`, then `agent/agent/workflow.yaml`) so older layouts keep working during migration, but new projects should use only `agent/workflow.yaml`.

## Related recipe changes

- **11.9.3** — main agent `workflow.yaml` relocation and DRAgent Taskfile updates (`018bff4`).
- **agent2** — same flat layout for a second agent directory (`2877388`: `agent2/agent/workflow.yaml` → `agent2/workflow.yaml`).

For other 11.8.8 agent-format changes, see the [framework migration guides](./README.md#migrations).
