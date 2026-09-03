# Base agent migration to 11.8.8

This guide covers migrating a base agent from the pre-11.8.8 layout to the simplified layout introduced in [af-component-agent#474](https://github.com/datarobot-community/af-component-agent/pull/474).

## Summary of changes

Unlike the other frameworks, the base agent still uses a `MyAgent` class extending `BaseAgent`. However, the class is simplified:

- The `__init__` method with its many parameters is removed. `BaseAgent` handles initialization.
- The `Config` class import is removed. Configuration is handled internally by `get_llm()`.
- LLM creation is decoupled: `get_llm()` from `datarobot_genai.langgraph.llm` is used in `custompy_adaptor` instead of being managed inside the class.
- The `_llm` instance variable and manual `self.config` setup are removed.

## Migration steps

Complete the following steps to migrate the base agent.

### 1. Update imports

**Before**:

```python
from openai.types.chat import CompletionCreateParams

from agent.config import Config
```

**After**:

```python
from datarobot_genai.langgraph.llm import get_llm
from openai.types.chat import CompletionCreateParams
```

Remove the `Config` import. Add the `get_llm` import.

### 2. Simplify `MyAgent` class

**Before**:

```python
class MyAgent(BaseAgent[None]):
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        verbose: bool = True,
        timeout: Optional[int] = 90,
        llm: Optional[Any] = None,
        tools: Optional[list[Any]] = None,
        forwarded_headers: Optional[dict[str, str]] = None,
    ):
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model=model,
            verbose=verbose,
            timeout=timeout,
            tools=tools,
            forwarded_headers=forwarded_headers,
        )
        self._llm = llm
        self.config = Config()

    async def invoke(self, run_agent_input: RunAgentInput) -> InvokeReturn:
        ...
```

**After**:

```python
class MyAgent(BaseAgent[None]):
    async def invoke(self, run_agent_input: RunAgentInput) -> InvokeReturn:
        ...
```

The entire `__init__` method is removed. `BaseAgent` provides the constructor.

### 3. Update `custompy_adaptor`

**Before**:

```python
async def custompy_adaptor(completion_create_params, ...):
    ...
    agent = MyAgent(
        model=completion_create_params.get("model"),
        verbose=...,
        timeout=...,
        forwarded_headers=...,
    )
```

**After**:

```python
_PLACEHOLDER_MODELS = frozenset({"unknown"})

async def custompy_adaptor(completion_create_params, ...):
    ...
    model_name = completion_create_params.get("model")
    agent = MyAgent(
        llm=get_llm(
            model_name=model_name if model_name not in _PLACEHOLDER_MODELS else None
        ),
        verbose=...,
        timeout=...,
        forwarded_headers=...,
    )
```

Key differences:
- `model=` parameter → `llm=get_llm(model_name=...)` parameter.
- `_PLACEHOLDER_MODELS` filters out the `"unknown"` model placeholder sent by DataRobot.

### 4. Update tests

- Remove tests for `__init__` parameters and `self.config`.
- Replace `MyAgent(model=..., api_key=...)` with `MyAgent(llm=Mock(), ...)`.
- Test `custompy_adaptor` with mock `get_llm` to verify placeholder model filtering.
- The `invoke()` tests remain largely the same since the method signature is unchanged.

## Complete before/after

See the [full diff](https://github.com/datarobot-community/af-component-agent/pull/474) and the [base agent documentation](./base.md) for the complete new layout.
