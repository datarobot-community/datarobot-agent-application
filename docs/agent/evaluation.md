# Local evaluation for agentic workflows

This guide covers how to evaluate agentic workflows locally using **`nat eval`** and DataRobot moderation metrics from `datarobot-genai`. It explains how to configure batch evaluation and optionally wrap runs in Pytest during development.

> [!NOTE]
> This guide covers **local, offline evaluation** during development. It is not intended for CI/CD pipelines. To enforce guardrails on live agent traffic through DRAgent, see [Moderation and guardrails](./moderation.md).

| Section | Description |
|---|---|
| [Why local evaluation](#why-local-evaluation) | When to use local evaluation vs. the Agentic Playground. |
| [Prerequisites](#prerequisites) | Required environment variables and resources. |
| [Configuration](#configuration) | `eval/*.yaml` structure and available metrics. |
| [Usage examples](#usage-examples) | CLI and optional Pytest patterns for local evaluation. |
| [Troubleshooting](#troubleshooting) | Common errors and fixes. |
| [Best practices](#best-practices) | Patterns and anti-patterns. |
| [Further reading](#further-reading) | Related docs and components. |

<a name="why-local-evaluation"></a>

## Why local evaluation

The DataRobot Agentic Playground provides a UI-based environment for evaluating deployed agents with built-in quality metrics and traces. Local evaluation with `nat eval` is the preferred approach when you need:

- **Fast feedback loops**&mdash;no deployment required; evaluation runs against your local `workflow.yaml` during development.
- **Reproducible datasets**&mdash;define evaluation cases and metrics as code in version control.
- **End-to-end coverage**&mdash;`nat eval` runs the same workflow path as `nat dragent serve`, then scores outputs in-process.

The Playground remains the preferred environment for evaluating live deployed agents, inspecting real LLM traces, and exploring quality metrics interactively across conversation turns.

<a name="prerequisites"></a>

## Prerequisites

### Dependencies

Local evaluation uses **`nat eval`** plugins shipped in `datarobot-genai` **0.26.10 or newer** (`dr_eval_plugins` entry point). The agent template already depends on `datarobot-genai[dragent, …]`; ensure your lockfile resolves to a version that includes the eval plugins.

Pytest evaluation tests use `@pytest.mark.timeout`; `pytest-timeout` is included in the template's `dev` optional dependencies (`dr task run agent:install`).

No separate `datarobot-moderations` install is required&mdash;evaluators call the same OOTB scorers in-process.

### Required environment variables

`DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` must be available before running evaluation. They are written to your `.env` file by `dr start`. The Taskfile loads `.env` automatically; if you run `nat eval` or `pytest` directly, export them first.

| Variable | Description |
|---|---|
| `DATAROBOT_ENDPOINT` | Your DataRobot instance URL (e.g., `https://app.datarobot.com/api/v2`). |
| `DATAROBOT_API_TOKEN` | A valid DataRobot API token. |

### Judge LLM

Evaluators reference a judge LLM by `llm_name` (typically `judge_llm`) defined in `eval/eval-config-base.yaml` as a `datarobot-llm-component`. Use a high-capability model that is **different from the model your agent uses**&mdash;a model scores its own outputs leniently, so an independent judge gives a more objective result.

<a name="configuration"></a>

## Configuration

Local evaluation is configured through YAML files under `eval/`. Each file extends a shared base that inherits your agent's `workflow.yaml`.

### File layout

```
agent/
├── workflow.yaml
├── eval/
│   ├── eval-config-base.yaml
│   ├── eval-config-agent-goal-accuracy.yaml
│   ├── dataset/
│   │   └── dataset-agent-goal-accuracy.json
│   └── ...
└── tests/
    └── test_agent_eval.py
```

### Base config

`eval/eval-config-base.yaml` inherits the agent workflow and adds a judge LLM plus output settings:

```yaml
base: ../workflow.yaml

llms:
  judge_llm:
    _type: datarobot-llm-component
    temperature: 0

eval:
  general:
    max_concurrency: 1
    output:
      dir: ./.tmp/nat-eval
      cleanup: true
```

`nat eval` runs the inherited workflow on each dataset row, then scores the generated response with the configured evaluators.

### Metric config

Each metric adds a dataset and evaluator block:

```yaml
# eval/eval-config-agent-goal-accuracy.yaml
base: eval-config-base.yaml

eval:
  general:
    dataset:
      _type: json
      file_path: ./eval/dataset/dataset-agent-goal-accuracy.json
  evaluators:
    agent_goal_accuracy:
      _type: agent_goal_accuracy
      llm_name: judge_llm
```

### Available evaluators

| Evaluator (`_type`) | Description | Dataset fields |
|---|---|---|
| `agent_goal_accuracy` | Whether the agent achieved the user's stated goal. | `question`, `answer` |
| `faithfulness` | Detects hallucinations by comparing the response to retrieved context. | `question`, `answer`, `context` (list of strings) |
| `task_adherence` | How closely the response follows prompt instructions. | `question`, `answer` |
| `agent_guideline_adherence` | Whether the response follows a fixed guideline string. | `question`, `answer`; set `agent_guideline` on the evaluator |

### Dataset format

Datasets are JSON arrays. Each row needs a unique `id`, a `question` (the user prompt `nat eval` sends to your workflow), and an `answer` (the reference response for the row):

```json
[
  {
    "id": "goal-accuracy-1",
    "question": "What is the return policy?",
    "answer": "Returns are accepted within 30 days of purchase."
  }
]
```

For faithfulness, include retrieved context:

```json
[
  {
    "id": "faithfulness-1",
    "question": "What is the return policy?",
    "answer": "Returns are accepted within 30 days of purchase.",
    "context": ["Returns are accepted within 30 days of purchase."]
  }
]
```

NAT maps `question` to the workflow input and `answer` to the expected output (`expected_output_obj`). After a run, `nat eval` can populate `generated_answer` with the workflow response.

<a name="usage-examples"></a>

## Usage examples

### Run evaluation from the CLI

```sh
cd agent && uv run nat eval --config_file eval/eval-config-agent-goal-accuracy.yaml
```

On success, the CLI prints an `EVALUATION SUMMARY` with per-metric scores. Results are also written under `.tmp/nat-eval` at the agent root (configurable via `eval.general.output.dir`).

### Optional Pytest wrapper

You can wrap `nat eval` in Pytest for repeatable local runs during development. Add tests to `agent/tests/test_agent_eval.py`:

```python
import os
import subprocess
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = AGENT_DIR / "eval"


def _run_nat_eval(config_file: Path, output_dir: Path):
    return subprocess.run(
        [
            "uv", "run", "nat", "eval",
            "--config_file", str(config_file),
            "--override", "eval.general.output.dir", str(output_dir),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(AGENT_DIR),
        env={**os.environ},
        check=False,
    )


@pytest.mark.eval
@pytest.mark.timeout(120)
def test_agent_goal_accuracy(tmp_path: Path) -> None:
    result = _run_nat_eval(
        EVAL_DIR / "eval-config-agent-goal-accuracy.yaml",
        tmp_path / "agent_goal_accuracy",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "EVALUATION SUMMARY" in output
```

### Registering the `eval` marker

To avoid Pytest warnings, register the custom marker in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "eval: marks tests as live evaluation tests requiring DataRobot credentials",
]
```

<a name="troubleshooting"></a>

## Troubleshooting

### `nat eval` command not found or unknown evaluator `_type`

**Cause:** `datarobot-genai` is older than 0.26.10, which first shipped the DataRobot moderation eval plugins.

**Fix:** Upgrade `datarobot-genai` in `pyproject.toml` and refresh the lockfile (`dr task run agent:install`).

### Missing evaluation dependencies

**Symptom:** `ModuleNotFoundError` for `ragas`, `deepeval`, or another evaluation library.

**Cause:** Dependencies are out of sync with `pyproject.toml`.

**Fix:**

```sh
dr task run agent:install
```

### Timeout errors

**Cause:** The judge or agent LLM deployment is cold-starting and takes longer than the pytest subprocess timeout.

**Fix:** Increase `@pytest.mark.timeout(180)` on eval tests. Keep `max_concurrency: 1` in `eval-config-base.yaml` to avoid overloading cold deployments.

### Faithfulness scores are always low

**Cause:** Dataset rows are missing `context`, or the context does not match what the agent actually retrieves.

**Fix:** Ensure each faithfulness row includes a `context` list with the passages the agent should ground on.

### `PytestUnknownMarkWarning: Unknown pytest.mark.eval`

**Cause:** The `eval` marker is not registered in `pyproject.toml`.

**Fix:** Add the marker to `[tool.pytest.ini_options]` as shown in the [Registering the `eval` marker](#registering-the-eval-marker) section.

<a name="best-practices"></a>

## Best practices

### Use a dedicated judge model

Define `judge_llm` separately from the agent's `datarobot_llm` in `eval-config-base.yaml`. Set `temperature: 0` on the judge for consistent scoring.

### Keep datasets in version control

Store `eval/dataset/*.json` alongside your agent code so evaluation cases are reviewed in pull requests alongside agent changes.

### Separate eval tests from unit tests with markers

Use `@pytest.mark.eval` on tests that call the DataRobot API so you can run them separately from unit tests during local development:

```sh
cd agent && uv run pytest tests/ -m eval        # Only evaluation tests (requires credentials)
cd agent && uv run pytest tests/ -m "not eval"  # Only unit tests (no credentials needed)
```

Do not run `nat eval` or eval-marked tests in CI&mdash;they require live DataRobot credentials and LLM deployments.

### Align runtime and offline guardrails

Runtime guardrails use `moderation_config.yaml` with `datarobot_moderation` middleware. Offline `nat eval` uses the same OOTB scorers in-process. Tune thresholds separately&mdash;runtime guards block live traffic; eval datasets assert quality on representative prompts.

<a name="further-reading"></a>

## Further reading

| Topic | Description |
|---|---|
| [Moderation and guardrails](./moderation.md) | Runtime guardrails with DRAgent middleware. |
| [Debugging agents](./debugging.md) | Step through agent code locally in VS Code and PyCharm. |
| [Implement tracing](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-tracing-code.html) | Add OpenTelemetry spans for observability in deployed agents. |
| [Agentic Playground](https://docs.datarobot.com/en/docs/agentic-ai/agentic-eval/agentic-playground.html) | UI-based evaluation environment for deployed agents with built-in metrics. |
| [AG-UI protocol](./ag-ui.md) | Event types emitted during agent execution. |
| [DataRobot agentic skills](https://docs.datarobot.com/en/docs/agentic-ai/agentic-develop/agentic-skills.html) | Install the `datarobot-app-framework-agent-local-evaluation` skill from `.agents/skills/` for coding-agent setup help. |
