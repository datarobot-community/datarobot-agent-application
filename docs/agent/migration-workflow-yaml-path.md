# `workflow.yaml` path migration (11.9.3)

This guide covers the breaking layout change introduced in agent component **11.9.3**.

## Summary

`workflow.yaml` moved out of the inner Python package to the **agent component root**:

| | Path (from repository root) |
|---|---|
| **Before** | `agent/agent/workflow.yaml` |
| **After** | `agent/workflow.yaml` |

`workflow.yaml` is the top-level NeMo Agent Toolkit (NAT) configuration loaded by the [DRAgent front server](./README.md#front-server) to build the FastAPI front server, tools, LLMs, middleware, and workflow graph for every framework.

If you upgrade a project that still has `agent/agent/workflow.yaml`, DRAgent fails to find the workflow file unless you relocate it.

## Migration steps

### 1. Move the file

```sh
git mv agent/agent/workflow.yaml agent/workflow.yaml
```

Remove any leftover copy under `agent/agent/` so only one `workflow.yaml` exists.

### 2. Update `workflow_path` in NAT `myagent.py` (DRUM fallback only)

> [!NOTE]
> Only relevant if you use the deprecated [DRUM fallback](./README.md#drum-fallback-deprecated-temporary) with the NAT framework. DRAgent loads `workflow.yaml` directly via `--config_file` and ignores `workflow_path`.

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

Infrastructure resolves the file with a primary/fallback lookup (`agent/workflow.yaml`, then `agent/agent/workflow.yaml`) so older layouts keep working during migration, but new projects should use only `agent/workflow.yaml`.

For other 11.8.8 agent-format changes, see the [framework migration guides](./README.md#migrations).
