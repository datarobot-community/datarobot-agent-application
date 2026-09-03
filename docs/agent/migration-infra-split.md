# Agent infra module split (11.11.48)

This guide covers the breaking layout change introduced in agent component 11.11.48.

## Summary

The agent's Pulumi infrastructure used to live in a single module. It is now an entry router plus a package:

| | Path (from repository root) |
|---|---|
| Before | `infra/infra/<agent_app_name>.py` — everything |
| After | `infra/infra/<agent_app_name>.py` — entry router only |
| | `infra/infra/<agent_app_name>_infra/base.py` — config shared by both runtimes |
| | `infra/infra/<agent_app_name>_infra/deployment.py` — the Custom Models runtime |
| | `infra/infra/<agent_app_name>_infra/workload.py` — the Workload API runtime |

Behaviour is unchanged. The router selects a runtime, and with no runtime selected it provisions Custom Models exactly as before. The public surface is unchanged too: everything `infra.<agent_app_name>` exported before is still exported, so other components that read those names need no changes.

**This only matters if you edited `infra/infra/<agent_app_name>.py` in your project.** If you never touched it, the update applies cleanly and there is nothing to do.

## What the update does

The file is rewritten almost entirely, so `copier update` 3-way-merges it. The conflict that survives is usually small and looks routine — but resolving it in favour of the incoming version silently discards your changes, because the code you patched now lives in `base.py` or `deployment.py`.

To make sure nothing is lost, the update first saves your version as:

```
infra/infra/<agent_app_name>.py.pre-split.bak
```

## Migration steps

### 1. Resolve the conflict in favour of the new router

`infra/infra/<agent_app_name>.py` is now template-owned and should contain only the runtime router. Take the incoming version wholesale:

```sh
git checkout --theirs infra/infra/<agent_app_name>.py
```

### 2. Find what you had changed

```sh
diff infra/infra/<agent_app_name>.py.pre-split.bak \
     <(git show <tag-you-updated-from>:infra/infra/<agent_app_name>.py)
```

Anything that shows up here is a local customization that needs a new home.

### 3. Port each change into the module that now owns it

| What you customized | Where it lives now |
|---|---|
| Execution environment resolution, MCP wiring, memory space, credentials, shared runtime parameters | `<agent_app_name>_infra/base.py` |
| Custom model, playground, LLM blueprint, prediction environment, deployment, resource bundle and replica sizing | `<agent_app_name>_infra/deployment.py` |
| Which runtime is selected | `<agent_app_name>.py` (the router) |

Most customizations — resource bundle IDs, replica counts, extra runtime parameters, deployment settings — belong in `deployment.py`.

### 4. Delete the backup

```sh
rm infra/infra/<agent_app_name>.py.pre-split.bak
```

### 5. Check the result

```sh
task infra:lint-check
task infra:test-coverage
```

If you also customized `infra/tests/units/test_<agent_app_name>.py`, note that it was split the same way: the entry file now covers runtime selection only, with the rest in `test_<agent_app_name>_base.py` and `test_<agent_app_name>_deployment.py`.
