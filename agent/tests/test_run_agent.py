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
"""Smoke tests for the agent's DataRobot-facing entrypoint scripts.

`run_agent.py` and `start_server.sh` are not called by the agent's own code, so
nothing else in this project fails if they are edited or deleted. DataRobot
calls them: `run_agent.py` runs one chat completion in the agentic playground
and in codespaces, `start_server.sh` starts the front server in a deployment.
Breaking either surfaces only after a deploy, so guard them here.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).parent.parent
RUN_AGENT = AGENT_ROOT / "run_agent.py"

# The arguments DataRobot passes when it runs the script. Dropping one breaks
# the playground.
DATAROBOT_ARGUMENTS = (
    "--chat_completion",
    "--custom_model_dir",
    "--default_headers",
    "--output_path",
    "--otel_entity_id",
    "--otel_attributes",
)


@pytest.mark.parametrize("entrypoint", ["run_agent.py", "start_server.sh"])
def test_entrypoint_script_is_present(entrypoint: str) -> None:
    assert (AGENT_ROOT / entrypoint).is_file(), (
        f"{entrypoint} is a DataRobot entrypoint for this agent and must not be"
        " deleted. See docs/agent/README.md."
    )


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    """Run run_agent.py in a subprocess, reusing this test run's venv.

    run_agent.py bootstraps a venv with `uv sync` when ``VENV_DIR`` is not
    already importable, which would take minutes and write outside the project.
    Pointing ``VENV_DIR`` at the active venv makes it take the branch it takes
    in a real playground session, where the venv is already in place.
    """
    return subprocess.run(
        [sys.executable, str(RUN_AGENT), *args],
        capture_output=True,
        text=True,
        cwd=AGENT_ROOT,
        # A sync we failed to suppress would hang CI; fail instead.
        timeout=120,
        env={**os.environ, "VENV_DIR": sys.prefix, "COLUMNS": "200"},
    )


def test_run_agent_imports_and_exposes_the_datarobot_arguments() -> None:
    """`--help` is enough to import every dependency the script runs on.

    That is the check worth having: run_agent.py pins itself to this project's
    `uv.lock`, so an incompatible datarobot-genai, openai, or opentelemetry
    fails here instead of in a playground session.
    """
    result = run_script("--help")

    assert result.returncode == 0, result.stderr
    for argument in DATAROBOT_ARGUMENTS:
        assert argument in result.stdout


def test_run_agent_requires_the_arguments_it_cannot_default() -> None:
    result = run_script("--custom_model_dir", str(AGENT_ROOT))

    assert result.returncode == 2
    assert "--chat_completion" in result.stderr
