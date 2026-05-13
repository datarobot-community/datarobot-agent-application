# NAT agent migration to 11.8.8

This guide covers migrating a NAT agent from the pre-11.8.8 layout to the simplified layout introduced in [af-component-agent#474](https://github.com/datarobot-community/af-component-agent/pull/474).

## Summary of changes

The NAT agent changes are minimal compared to other frameworks. The `MyAgent` class still extends `NatAgent`, but:

- The `__init__` method is simplified to use `*args` / `**kwargs` pass-through.
- The `model=` parameter is removed from `custompy_adaptor` since NAT handles LLM configuration declaratively in `workflow.yaml`.

## Migration steps

### 1. Simplify `__init__`

**Before:**

```python
class MyAgent(NatAgent):
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        verbose: bool = True,
        timeout: int | None = 90,
        forwarded_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            workflow_path=Path(__file__).parent / "workflow.yaml",
            api_key=api_key,
            api_base=api_base,
            model=model,
            verbose=verbose,
            timeout=timeout,
            forwarded_headers=forwarded_headers,
        )
```

**After:**

```python
class MyAgent(NatAgent):
    def __init__(
        self,
        *args: Any,
        workflow_path: Path = Path(__file__).parent / "workflow.yaml",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *args,
            workflow_path=workflow_path,
            **kwargs,
        )
```

The explicit parameter list is replaced with `*args` / `**kwargs`, and `workflow_path` is a keyword-only argument with a default.

### 2. Update `custompy_adaptor`

**Before:**

```python
async def custompy_adaptor(completion_create_params, ...):
    ...
    agent = MyAgent(
        model=completion_create_params.get("model"),
        verbose=completion_create_params.get("verbose", True),
        timeout=completion_create_params.get("timeout", 90),
        forwarded_headers=forwarded_headers,
    )
```

**After:**

```python
async def custompy_adaptor(completion_create_params, ...):
    ...
    agent = MyAgent(
        verbose=completion_create_params.get("verbose", True),
        timeout=completion_create_params.get("timeout", 90),
        forwarded_headers=forwarded_headers,
    )
```

The `model=` parameter is removed. NAT agents resolve LLMs from `workflow.yaml` rather than from the request.

### 3. Update tests

- Update test fixtures that pass explicit `__init__` parameters to use the new `*args` / `**kwargs` signature.
- Remove tests for `model=` parameter handling in `custompy_adaptor`.

## Complete before/after

See the [full diff](https://github.com/datarobot-community/af-component-agent/pull/474) and the [NAT agent documentation](./nat.md) for the complete new layout. Custom tools (`nat_tool`, `functions` in `workflow.yaml`, loading `register.py`) are covered under [Custom local tools](./nat.md#custom-local-tools).
