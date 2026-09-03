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
"""Checks how start_server.sh boots the deployed agent.

start_server.sh is the custom model entrypoint. It replaces the copy baked into
the execution environment image, so it has to work across the execution
environment versions projects pin -- which differ in whether the image's uv
cache is writable by the deployment user. Everything it shells out to (uv, nat)
is stubbed, so nothing is installed and no server is started.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

START_SERVER = Path(__file__).parent.parent / "start_server.sh"

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="POSIX shell entrypoint, not used on Windows"
)

# Stands in for `uv`. `uv venv` writes the venv the script then sources, but
# reads the shared cache first, so an execution environment that leaves that
# cache root-owned fails here and takes the deployment down with it.
# `broken_cache` replays that failure; `always_fails` covers the case where even
# the retry cannot produce a venv.
FAKE_UV = """#!/bin/sh
echo "$@" >> "{log}"
if [ "$1" = venv ]; then
    if [ "{mode}" = always_fails ]; then
        exit 2
    fi
    if [ "{mode}" = broken_cache ] && [ -z "$UV_NO_CACHE" ]; then
        echo "error: Failed to initialize cache at $UV_CACHE_DIR" >&2
        echo "  Caused by: failed to open file \\`$UV_CACHE_DIR/sdists-v9/.git\\`:\
 Permission denied (os error 13)" >&2
        exit 2
    fi
    mkdir -p "$2/bin" && : > "$2/bin/activate"
fi
exit 0
"""

# Stands in for `nat`, recording the command line instead of serving.
FAKE_NAT = """#!/bin/sh
echo "$@" > "{args}"
"""


class Result:
    """Outcome of one start_server.sh run."""

    def __init__(
        self, process: subprocess.CompletedProcess[str], uv_log: Path, nat_args: Path
    ) -> None:
        self.returncode = process.returncode
        self.stdout = process.stdout
        self.stderr = process.stderr
        self.uv_commands = uv_log.read_text().splitlines() if uv_log.exists() else []
        self.nat_args = nat_args.read_text() if nat_args.exists() else ""


def run_start_server(code_dir: Path, tmp_path: Path, uv_mode: str = "ok") -> Result:
    """Run start_server.sh in `code_dir` with uv and nat stubbed out."""
    shutil.copy(START_SERVER, code_dir / "start_server.sh")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv_log"
    nat_args = tmp_path / "nat_args"
    (bin_dir / "uv").write_text(FAKE_UV.format(log=uv_log, mode=uv_mode))
    (bin_dir / "nat").write_text(FAKE_NAT.format(args=nat_args))
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)

    process = subprocess.run(
        ["sh", str(code_dir / "start_server.sh")],
        capture_output=True,
        text=True,
        timeout=60,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "VENV_DIR": str(tmp_path / "venv"),
            "CODE_DIR": str(code_dir),
            "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        },
    )
    return Result(process, uv_log, nat_args)


@pytest.fixture
def code_dir(tmp_path: Path) -> Path:
    """A custom model directory laid out the way this component generates it."""
    path = tmp_path / "code"
    path.mkdir()
    (path / "workflow.yaml").touch()
    return path


def test_serves_workflow_yaml_from_the_app_root(code_dir: Path, tmp_path: Path) -> None:
    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"--config_file {code_dir / 'workflow.yaml'}" in result.nat_args


def test_falls_back_to_the_pre_11_9_3_agent_subdirectory(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    (code_dir / "agent").mkdir(parents=True)
    (code_dir / "agent" / "workflow.yaml").touch()

    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"--config_file {code_dir / 'agent' / 'workflow.yaml'}" in result.nat_args


def test_fails_loudly_when_no_workflow_yaml_exists(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 1
    assert "no workflow.yaml found" in result.stderr


def test_uses_the_shared_uv_cache_when_it_is_usable(
    code_dir: Path, tmp_path: Path
) -> None:
    result = run_start_server(code_dir, tmp_path)

    assert result.returncode == 0, result.stderr
    # One `uv venv`: no retry was needed, so the pre-warmed cache stays in play
    # for the sync that follows.
    assert result.uv_commands.count(f"venv {tmp_path / 'venv'}") == 1


def test_starts_anyway_when_the_images_uv_cache_is_not_writable(
    code_dir: Path, tmp_path: Path
) -> None:
    result = run_start_server(code_dir, tmp_path, uv_mode="broken_cache")

    assert result.returncode == 0, result.stderr
    assert "retrying with the shared uv cache disabled" in result.stdout
    assert f"--config_file {code_dir / 'workflow.yaml'}" in result.nat_args


def test_reports_the_real_problem_when_no_venv_can_be_created(
    code_dir: Path, tmp_path: Path
) -> None:
    result = run_start_server(code_dir, tmp_path, uv_mode="always_fails")

    assert result.returncode == 1
    assert "could not create a virtual environment" in result.stderr
    # Not the misleading "can't open .../bin/activate" the bare `.` produced.
    assert "activate" not in result.stderr
