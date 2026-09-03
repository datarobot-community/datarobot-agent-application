# `workflow.yaml` path migration (11.9.3)

This guide covers the breaking layout change introduced in agent component 11.9.3.

## Summary

`workflow.yaml` moved out of the inner Python package to the agent component root:

| | Path (from repository root) |
|---|---|
| Before | `agent/agent/workflow.yaml` |
| After | `agent/workflow.yaml` |

`workflow.yaml` is the top-level NeMo Agent Toolkit (NAT) configuration loaded by the [DRAgent front server](./README.md#front-server) to build the FastAPI front server, tools, LLMs, middleware, and workflow graph for every framework.

Upgrading a project that still has `agent/agent/workflow.yaml` causes DRAgent to fail to find the workflow file unless the file is relocated.

## Migration steps

Complete the following steps to migrate a project that still has `workflow.yaml` at `agent/agent/workflow.yaml`.

### 1. Move the file

Move `workflow.yaml` to the agent component root:

```sh
git mv agent/agent/workflow.yaml agent/workflow.yaml
```

Remove any leftover copy under `agent/agent/` so only one `workflow.yaml` exists.

### 2. Update `workflow_path` in NAT `myagent.py` (if present)

If a NAT project sets `workflow_path` in `myagent.py`, point it at `agent/workflow.yaml`. DRAgent loads `workflow.yaml` via `--config_file` at the agent root (see step 3); the generated Taskfile does not rely on `workflow_path`.

Before (file co-located with `myagent.py`):

```python
workflow_path: Path = Path(__file__).parent / "workflow.yaml",
```

After (`workflow.yaml` one directory up):

```python
workflow_path: Path = Path(__file__).parent.parent / "workflow.yaml",
```

### 3. Update Taskfile and CLI references

Generated `agent/Taskfile.yml` passes `workflow.yaml` (relative to the `agent/` working directory), not `agent/workflow.yaml`. Align any customized paths accordingly:

```yaml
# DRAgent dev server
nat dragent serve --config_file workflow.yaml ...

# CLI default
export DRAGENT_CONFIG_FILE="${DRAGENT_CONFIG_FILE:-workflow.yaml}"
```

### 4. Search for stale paths

Check custom scripts, tests, and infrastructure for references to `agent/agent/workflow.yaml`:

```sh
rg 'agent/agent/workflow\.yaml' .
```

Infrastructure resolves the file with a primary/fallback lookup (`agent/workflow.yaml`, then `agent/agent/workflow.yaml`), so a project that still has `agent/agent/workflow.yaml` continues to work during migration; every other project uses only `agent/workflow.yaml`.

For other 11.8.8 agent-format changes, see the [framework migration guides](./README.md#migrations).
