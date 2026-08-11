---
name: datarobot-app-framework-agent-local-evaluation
description: >-
  Use this skill when a user asks how to evaluate their agent locally, how to write quality-gate tests for their 
  agent, how to detect hallucinations, or how to configure batch evaluation with DataRobot moderation 
  metrics (Faithfulness, Task Adherence, Agent Goal Accuracy, Agent Guideline Adherence).
---
# Skill: DataRobot local agentic evaluation

**When to use this skill:** Use this skill when a user asks how to evaluate their agent locally, how to write quality-gate tests for their agent, how to detect hallucinations, or how to configure batch evaluation with DataRobot moderation metrics (Faithfulness, Task Adherence, Agent Goal Accuracy, Agent Guideline Adherence).

**Context window cost:** ~900 tokens.

## Prerequisites

Before generating any code, confirm the following with the user:

1. Dependencies are installed — `datarobot-genai[nat, dragent]` (or the framework extra your agent uses) must be **0.26.10 or newer**, which ships `nat eval` plugins for DataRobot moderation metrics. Dev dependencies (including `pytest-timeout` for `@pytest.mark.timeout`) are installed via `dr task run agent:install`.
2. `DATAROBOT_ENDPOINT` and `DATAROBOT_API_TOKEN` are set as environment variables. `dr start` creates the project-root `.env` file where the user configures these values.
3. The agent has a `workflow.yaml` at the agent component root (standard for all DRAgent templates).

Evaluators use the `judge_llm` entry you add in `eval/eval-config-base.yaml` (`_type: datarobot-llm-component`). That LLM should be a high-capability model **different from the one your agent uses** for generation — judges score more objectively when they are independent of the agent model.

## Step-by-step implementation guide

When a user asks to set up local evaluation, generate the files below. Copy-paste-ready YAML and dataset templates are in `references/`; a runnable Pytest wrapper is in `examples/`.

### 1. Create `eval/eval-config-base.yaml`

Copy `references/eval-config-base.yaml` to `agent/eval/eval-config-base.yaml`. It inherits the agent's `workflow.yaml` and adds a dedicated judge LLM plus output settings:

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

### 2. Create metric-specific eval configs and datasets

Copy the matching config from `references/` and dataset from `references/dataset/` for each metric the user needs.

#### Agent goal accuracy

- **Evaluator `_type`:** `agent_goal_accuracy`
- **Config (copy to `agent/eval/`):** `references/eval-config-agent-goal-accuracy.yaml`
- **Dataset (copy to `agent/eval/dataset/`):** `references/dataset/dataset-agent-goal-accuracy.json`
- **Required JSON fields per row:** `id`, `question`, `answer`

#### Faithfulness (RAG / hallucination detection)

- **Evaluator `_type`:** `faithfulness`
- **Config (copy to `agent/eval/`):** `references/eval-config-faithfulness.yaml`
- **Dataset (copy to `agent/eval/dataset/`):** `references/dataset/dataset-faithfulness.json`
- **Required JSON fields per row:** `id`, `question`, `answer`, `context` (array of retrieved passage strings)

#### Task adherence

- **Evaluator `_type`:** `task_adherence`
- **Config (copy to `agent/eval/`):** `references/eval-config-task-adherence.yaml`
- **Dataset (copy to `agent/eval/dataset/`):** `references/dataset/dataset-task-adherence.json`
- **Required JSON fields per row:** `id`, `question`, `answer`

#### Guideline adherence

- **Evaluator `_type`:** `agent_guideline_adherence`
- **Config (copy to `agent/eval/`):** `references/eval-config-agent-guideline-adherence.yaml`
- **Dataset (copy to `agent/eval/dataset/`):** `references/dataset/dataset-agent-guideline-adherence.json`
- **Required JSON fields per row:** `id`, `question`, `answer`
- **Extra evaluator YAML field:** `agent_guideline` (string describing the rule to enforce, e.g. `"Respond in one sentence or less."`)

Each metric config extends the base:

```yaml
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

Replace placeholder `question`, `answer`, and `context` values with content relevant to the user's agent domain.

### 3. Generate the Pytest evaluation test

Copy `examples/test_agent_eval.py` to `agent/tests/test_agent_eval.py`.

Tests invoke `nat eval` as a subprocess (same CLI used for manual runs), so evaluation exercises the real `workflow.yaml` path end to end:

```python
@pytest.mark.eval
@pytest.mark.timeout(120)
def test_agent_goal_accuracy(tmp_path: Path) -> None:
    config_file = EVAL_DIR / "eval-config-agent-goal-accuracy.yaml"
    result = _run_nat_eval(config_file, tmp_path / "agent_goal_accuracy")
    assert result.returncode == 0
    assert "EVALUATION SUMMARY" in result.stdout + result.stderr
```

### 4. Register the `eval` marker

Add the marker to `[tool.pytest.ini_options]` in `pyproject.toml` to avoid `PytestUnknownMarkWarning`:

```toml
[tool.pytest.ini_options]
markers = [
    "eval: marks tests as live evaluation tests requiring DataRobot credentials",
]
```

## Common user questions

### "How do I run evaluation manually?"

From the agent directory:

```sh
cd agent && uv run nat eval --config_file eval/eval-config-agent-goal-accuracy.yaml
```

Or via Taskfile (if the `eval` task is present):

```sh
dr task run agent:eval -- eval/eval-config-agent-goal-accuracy.yaml
```

### "How do I run only the evaluation tests?"

```sh
cd agent && uv run pytest tests/test_agent_eval.py -m eval -v
```

### "The judge keeps timing out."

Reduce `max_concurrency` in `eval-config-base.yaml` to `1` (already the default in `references/`). Cold-start LLM deployments can take up to two minutes — increase the pytest timeout (`@pytest.mark.timeout(180)`) if needed.

## Key facts to communicate to the user

- `nat eval` runs the agent workflow on each dataset question, then scores outputs in-process via DataRobot moderation OOTB judges — no NeMo Evaluator microservice and no separate `moderation.yaml` for offline eval.
- Evaluator plugins ship in `datarobot-genai` (`dr_eval_plugins` entry point) and require **datarobot-genai >= 0.26.10**.
- `llm_name: judge_llm` on each evaluator points at the judge LLM defined in `eval-config-base.yaml`, not at a raw deployment ID.
- Faithfulness rows need a `context` field (list of strings). All rows should include `question` and `answer`.
- See [`docs/agent/evaluation.md`](../../../docs/agent/evaluation.md) for full configuration options and troubleshooting.
