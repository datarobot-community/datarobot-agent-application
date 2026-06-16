# Local evaluation for agentic workflows

This guide covers how to evaluate agentic workflows locally using the `datarobot-moderations` SDK and Pytest. It explains how to configure LLM-as-a-judge metrics, write assertions in test suites, and integrate quality gates into CI/CD pipelines.

> [!NOTE]
> This guide covers **offline evaluation** in tests. To enforce guardrails on live agent traffic through DRUM or DRAgent, see [Moderation and guardrails](./moderation.md).

| Section | Description |
|---|---|
| [Why local evaluation](#why-local-evaluation) | When to use local evaluation vs. the Agentic Playground. |
| [Prerequisites](#prerequisites) | Required environment variables and resources. |
| [Configuration](#configuration) | `moderation.yaml` structure and available metrics. |
| [Usage examples](#usage-examples) | Pytest patterns for local evaluation. |
| [CI/CD integration](#cicd-integration) | Running evaluation gates in automated pipelines. |
| [Troubleshooting](#troubleshooting) | Common errors and fixes. |
| [Best practices](#best-practices) | Patterns and anti-patterns. |
| [Further reading](#further-reading) | Related docs and components. |

<a name="why-local-evaluation"></a>

## Why local evaluation

The DataRobot Agentic Playground provides a UI-based environment for evaluating deployed agents with built-in quality metrics and traces. Local evaluation with Pytest is the preferred approach when you need:

- **Fast feedback loops**&mdash;no deployment required; evaluation runs against your local agent code during development.
- **CI/CD quality gates**&mdash;block a pipeline (`dr run deploy`) if agent responses fall below a quality threshold.
- **Reproducible assertions**&mdash;define exact pass/fail thresholds as code in version control.
- **Programmatic control**&mdash;compose evaluation with other test logic, parametrize across test cases, and generate structured reports.

The Playground remains the preferred environment for evaluating live deployed agents, inspecting real LLM traces, and exploring quality metrics interactively across conversation turns.

<a name="prerequisites"></a>

## Prerequisites

### Dependencies

The `datarobot-moderations[all]` package is already included in `pyproject.toml` as a core agent dependency. No additional installation is needed.

### Required environment variables

All three variables must be available as environment variables before running evaluation tests. `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` are written to your `.env` file by `dr start`. Add `TARGET_NAME` to `.env` as well. The Taskfile loads `.env` automatically; if you run `pytest` directly, export them first.

| Variable | Description |
|---|---|
| `DATAROBOT_ENDPOINT` | Your DataRobot instance URL (e.g., `https://app.datarobot.com/api/v2`). |
| `DATAROBOT_API_TOKEN` | A valid DataRobot API token. |
| `TARGET_NAME` | The key in your deployment's JSON response that holds the generated text (e.g., `resultText`). The moderations library reads this field to extract the text it will score. DRUM sets it automatically; Pytest does not. |

### Required resources

You need a DataRobot LLM deployment to act as the **evaluator judge**. Use a high-capability model that is **different from the model your agent uses** — a model scores its own outputs leniently, so an independent judge gives a more objective result. Record the 24-character deployment ID; you will reference it in `moderation.yaml`.

<a name="configuration"></a>

## Configuration

Local evaluation is configured through a `moderation.yaml` file that defines which metrics to calculate and the thresholds for pass/fail decisions.

### File location

Place `moderation.yaml` at the root of the agent directory alongside `custom.py`:

```
agent/
├── moderation.yaml     # Evaluation configuration
├── custom.py
├── cli.py
└── ...
```

### Example configuration

```yaml
# moderation.yaml
timeout_sec: 60
timeout_action: block

guards:
  - name: Agent Goal Accuracy
    type: ootb
    ootb_type: agent_goal_accuracy
    stage: response
    is_agentic: true
    llm_type: datarobot
    deployment_id: "<YOUR_JUDGE_LLM_DEPLOYMENT_ID>"
    intervention:
      action: block
      message: "Agent failed to achieve the user's goal."
      conditions:
        - comparator: lessThan
          comparand: 0.7   # Fail if accuracy score is below 70%
```

`deployment_id` is the DataRobot deployment the library calls to run the LLM-as-a-judge evaluation. It sends your agent's response to this deployment and asks it to score the quality metric.

### Available out-of-the-box metrics

| Metric (`ootb_type`) | Description | Requires `retrieved_contexts` |
|---|---|---|
| `agent_goal_accuracy` | Measures whether the agent achieved the user's stated goal. | No |
| `faithfulness` | Detects hallucinations by comparing the response against retrieved context. | Yes (`copy_citations: true`) |
| `task_adherence` | Measures how closely the response follows the instructions in the prompt. | No |

### Configuration reference

| Field | Description |
|---|---|
| `timeout_sec` | Seconds to wait for the evaluator LLM before applying `timeout_action`. |
| `timeout_action` | What to do on timeout: `score` (treat as pass) or `block` (treat as fail). |
| `guards[].name` | Unique label; used as the key in `result.metrics`. |
| `guards[].ootb_type` | The metric to calculate (see table above). |
| `guards[].deployment_id` | DataRobot LLM deployment ID for the judge model (exactly 24 hex characters). |
| `guards[].copy_citations` | Set `true` to pass retrieved RAG context to the guard. Required for `faithfulness`. |
| `guards[].is_agentic` | Set `true` for `agent_goal_accuracy` guards. |
| `guards[].intervention.conditions[].comparand` | Numeric threshold for pass/fail. |
| `guards[].intervention.conditions[].comparator` | Comparison operator: `lessThan`, `greaterThan`, `equals`. |

<a name="usage-examples"></a>

## Usage examples

Evaluation tests use `async def` with `await` because `pyproject.toml` sets `asyncio_mode = "auto"`, which makes pytest-asyncio handle all async test functions automatically.

### Basic evaluation in Pytest

Invoke your agent via `custompy_adaptor` and pass the response text to `ModerationPipeline` for scoring. `completion_params` is an OpenAI-compatible chat completion request dict — the same format accepted by the DRUM `chat()` hook. Add evaluation tests to `agent/tests/test_agent_eval.py`.

```python
# tests/test_agent_eval.py
import pytest
from datarobot_dome.api import ModerationPipeline

from agent import custompy_adaptor


@pytest.fixture(scope="session")
def pipeline():
    return ModerationPipeline.from_yaml("moderation.yaml")


@pytest.mark.eval
async def test_agent_goal_accuracy(pipeline):
    user_prompt = "What is the return policy?"
    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,  # extract text from CustomModelChatResponse
        prompt=user_prompt,
    )

    # result.blocked is True when any guard's threshold is breached
    assert not result.blocked, (
        f"Eval failed: {result.blocked_message} | Metrics: {result.metrics}"
    )
```

### Faithfulness (hallucination detection)

Set `copy_citations: true` in the guard's YAML config and pass `retrieved_contexts` to `evaluate_response` to enable faithfulness scoring:

```python
@pytest.mark.eval
async def test_agent_faithfulness(pipeline):
    user_prompt = "What is the return policy?"
    retrieved_context = ["Returns are accepted within 30 days of purchase."]

    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,
        prompt=user_prompt,
        retrieved_contexts=retrieved_context,  # required for faithfulness
    )

    assert not result.blocked, f"Hallucination detected: {result.blocked_message}"
```

### Parametrized test cases

Run the same evaluation logic across a dataset of prompt/response pairs:

```python
TEST_CASES = [
    {
        "prompt": "What is the return policy?",
        "context": ["Returns are accepted within 30 days of purchase."],
    },
    {
        "prompt": "How do I reset my password?",
        "context": ["Click 'Forgot password' on the login page."],
    },
]


@pytest.mark.eval
@pytest.mark.parametrize("case", TEST_CASES)
async def test_faithfulness_parametrized(pipeline, case):
    completion_params = {
        "model": None,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "stream": False,
    }
    response_obj = await custompy_adaptor(completion_params)

    result, _ = pipeline.evaluate_response(
        response_obj.response,
        prompt=case["prompt"],
        retrieved_contexts=case["context"],
    )
    assert not result.blocked, (
        f"Failed on prompt '{case['prompt']}': {result.blocked_message}"
    )
```

### Verifying that a hallucination is caught

A negative test requires no agent invocation — pass a known-wrong response directly to `evaluate_response` to verify the pipeline catches it:

```python
@pytest.mark.eval
def test_pipeline_catches_hallucination(pipeline):
    result, _ = pipeline.evaluate_response(
        "Returns are not accepted under any circumstances.",  # deliberately wrong
        prompt="What is the return policy?",
        retrieved_contexts=["Returns are accepted within 30 days of purchase."],
    )
    assert result.blocked, "The evaluation pipeline should have caught the hallucination."
```

### Registering the `eval` marker

To avoid Pytest warnings, register the custom marker in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "eval: marks tests as live evaluation tests requiring DataRobot credentials",
]
```

<a name="cicd-integration"></a>

## CI/CD integration

Run only evaluation tests (requires DataRobot credentials):

```sh
cd agent && uv run pytest tests/ -m eval
```

Run all tests except evaluation (no credentials needed):

```sh
cd agent && uv run pytest tests/ -m "not eval"
```

The Taskfile exposes a `test` task for the full suite:

```sh
dr task run agent:test
```

Example GitHub Actions step:

```yaml
- name: Run agent evaluation tests
  run: cd agent && uv run pytest tests/ -m eval --junitxml=eval-results.xml
  env:
    DATAROBOT_API_TOKEN: ${{ secrets.DATAROBOT_API_TOKEN }}
    DATAROBOT_ENDPOINT: ${{ secrets.DATAROBOT_ENDPOINT }}
    TARGET_NAME: resultText
```

> [!NOTE]
> Evaluation tests call the DataRobot API to invoke the judge LLM. Standard unit tests marked with `not eval` continue to pass without credentials.

<a name="troubleshooting"></a>

## Troubleshooting

### Missing evaluation dependencies

**Symptom:** `ModuleNotFoundError` for `ragas`, `rouge_score`, or another evaluation library.

**Cause:** Dependencies are out of sync with `pyproject.toml`.

**Fix:**

```sh
dr task run agent:install
```

### Timeout errors from the evaluator LLM

**Cause:** The judge model deployment is in a cold-start state and takes longer than `timeout_sec` to respond.

**Fix:** Increase `timeout_sec` in `moderation.yaml` (e.g., `120`). Alternatively, set `timeout_action: score` to treat timeouts as passing during development.

### `result.blocked` is unexpectedly `True` in all tests

**Cause:** The `deployment_id` in `moderation.yaml` is still the placeholder value.

**Fix:** Replace `<YOUR_JUDGE_LLM_DEPLOYMENT_ID>` with the 24-character hex ID of your evaluator LLM deployment from the DataRobot UI.

### Evaluation scores are always `0.0`

**Cause:** `TARGET_NAME` is not set, or the evaluator LLM deployment does not support the selected metric.

**Fix:** Export `TARGET_NAME` (e.g., `export TARGET_NAME=resultText`) before running tests, and verify the deployment supports the `ootb_type` you selected.

### `PytestUnknownMarkWarning: Unknown pytest.mark.eval`

**Cause:** The `eval` marker is not registered in `pyproject.toml`.

**Fix:** Add the marker to `[tool.pytest.ini_options]` as shown in the [Registering the `eval` marker](#registering-the-eval-marker) section.

<a name="best-practices"></a>

## Best practices

### Use a dedicated judge model

Use a high-capability model as your evaluator `deployment_id`, separate from the model your agent uses to generate responses. Evaluating with the same model that produced the response introduces bias.

### Set `timeout_action: block` in CI

In CI/CD pipelines, set `timeout_action: block` so that timeouts are treated as failures. This prevents silently passing tests when the judge model is unreachable.

### Keep thresholds in version control

Store `moderation.yaml` alongside your agent code so threshold changes are reviewed in pull requests alongside the agent changes that motivated them.

### Separate eval tests from unit tests with markers

Use `@pytest.mark.eval` on all tests that call the DataRobot API. This allows unit tests and eval tests to be run independently:

```sh
cd agent && uv run pytest tests/ -m eval        # Only evaluation tests (requires credentials)
cd agent && uv run pytest tests/ -m "not eval"  # Only unit tests (no credentials needed)
```

<a name="further-reading"></a>

## Further reading

| Topic | Description |
|---|---|
| [Moderation and guardrails](./moderation.md) | Runtime guardrails with DRUM and DRAgent. |
| [Debugging agents](./debugging.md) | Step through agent code locally in VS Code and PyCharm. |
| [Implement tracing](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html) | Add OpenTelemetry spans for observability in deployed agents. |
| [Agentic Playground](https://docs.datarobot.com/en/docs/agentic-ai/agentic-evaluate/agentic-playground.html) | UI-based evaluation environment for deployed agents with built-in metrics. |
| [AG-UI protocol](./ag-ui.md) | Event types emitted during agent execution. |
