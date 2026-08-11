# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copy this file to agent/tests/test_agent_eval.py and replace the placeholder
# prompts in eval/dataset/*.json with content relevant to your agent's domain.
#
# Prerequisites:
#   - Copy references/eval-config-*.yaml to agent/eval/
#   - Copy references/dataset/*.json to agent/eval/dataset/
#   - Install dev deps (includes pytest-timeout for @pytest.mark.timeout)
#   - datarobot-genai >= 0.26.10 (nat eval moderation plugins)
#   - DATAROBOT_ENDPOINT and DATAROBOT_API_TOKEN in .env
#   - Register the eval marker in pyproject.toml:
#       [tool.pytest.ini_options]
#       markers = ["eval: live evaluation tests requiring DataRobot credentials"]
#
# Run evaluation tests:
#   cd agent && uv run pytest tests/test_agent_eval.py -m eval -v
#
# Skip evaluation tests (no credentials needed):
#   cd agent && uv run pytest tests/ -m "not eval"

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = AGENT_DIR / "eval"


def _run_nat_eval(
    config_file: Path, output_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "nat",
            "eval",
            "--config_file",
            str(config_file),
            "--override",
            "eval.general.output.dir",
            str(output_dir),
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
    """Agent responses should achieve the user's stated goal."""
    config_file = EVAL_DIR / "eval-config-agent-goal-accuracy.yaml"
    output_dir = tmp_path / "agent_goal_accuracy"
    result = _run_nat_eval(config_file, output_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"nat eval failed (exit {result.returncode}).\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )
    assert "EVALUATION SUMMARY" in output
    assert "agent_goal_accuracy" in output.lower()


@pytest.mark.eval
@pytest.mark.timeout(120)
def test_agent_faithfulness(tmp_path: Path) -> None:
    """Agent responses should not hallucinate facts outside retrieved context."""
    config_file = EVAL_DIR / "eval-config-faithfulness.yaml"
    output_dir = tmp_path / "faithfulness"
    result = _run_nat_eval(config_file, output_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"nat eval faithfulness failed (exit {result.returncode}).\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )
    assert "EVALUATION SUMMARY" in output
    assert "faithfulness" in output.lower()


@pytest.mark.eval
@pytest.mark.timeout(120)
def test_agent_task_adherence(tmp_path: Path) -> None:
    """Agent responses should follow instructions in the prompt."""
    config_file = EVAL_DIR / "eval-config-task-adherence.yaml"
    output_dir = tmp_path / "task_adherence"
    result = _run_nat_eval(config_file, output_dir)
    output = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"nat eval task adherence failed (exit {result.returncode}).\n"
        f"stdout: {result.stdout[:2000]}\n"
        f"stderr: {result.stderr[:2000]}"
    )
    assert "EVALUATION SUMMARY" in output
    assert "task_adherence" in output.lower()
