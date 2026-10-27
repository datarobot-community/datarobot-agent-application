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
"""Tests for infra/infra/mcp_migration_check.py: stop a deploy that would delete the old MCP server."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pulumi
import pytest

MODULE = Path(__file__).resolve().parents[2] / "infra" / "mcp_migration_check.py"
PREFIX = "urn:pulumi:dev::agentic-application-starter::"
AGENT = (
    PREFIX + "datarobot:index/customModel:CustomModel::[my-app] [agent] Custom Model"
)
OLD_MODEL = (
    PREFIX
    + "datarobot:index/customModel:CustomModel::[my-app] [mcp_server] Custom Model"
)
OLD_DEPLOYMENT = (
    PREFIX
    + "custom:datarobot:CustomModelDeployment$datarobot:index/deployment:Deployment"
    + "::[my-app] [mcp_server] Deployment"
)
# A shared DataRobot environment the old server only read (ExecutionEnvironment.get):
# Pulumi marks it external, and a deploy never deletes it.
OLD_ENVIRONMENT = {
    "urn": PREFIX
    + "datarobot:index/executionEnvironment:ExecutionEnvironment"
    + "::[my-app] [mcp_server] Execution Environment",
    "external": True,
}


def exported(*resources, returncode=0):
    state = {
        "deployment": {
            "resources": [r if isinstance(r, dict) else {"urn": r} for r in resources]
        }
    }
    return subprocess.CompletedProcess(
        [], returncode, stdout=json.dumps(state), stderr=""
    )


@pytest.fixture
def check(monkeypatch, tmp_path):
    """The module, loaded from a copy so a test can put mcp_server.py next to it."""
    monkeypatch.delenv("MCP_MIGRATION_CONFIRMED", raising=False)
    monkeypatch.setattr(pulumi, "get_stack", lambda: "dev")
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/local/bin/{name}")
    for level in ("info", "warn", "error"):
        monkeypatch.setattr(pulumi.log, level, MagicMock())
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=exported()))
    copy = tmp_path / "mcp_migration_check.py"
    copy.write_text(MODULE.read_text())
    spec = importlib.util.spec_from_file_location(
        "mcp_migration_check_under_test", copy
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # an empty stack: nothing happens at import
    pulumi.log.info.assert_not_called()
    pulumi.log.warn.assert_not_called()
    return module


def stack_with(monkeypatch, *urns, returncode=0):
    run = MagicMock(return_value=exported(*urns, returncode=returncode))
    monkeypatch.setattr(subprocess, "run", run)
    return run


def test_stops_and_lists_the_old_server(monkeypatch, check):
    run = stack_with(monkeypatch, AGENT, OLD_MODEL, OLD_DEPLOYMENT)
    message = check.stop_message()
    assert message and message.startswith(
        "MCP migration: deploy stopped. Nothing changed."
    )
    assert "  - [my-app] [mcp_server] Custom Model\n" in message
    assert "  - [my-app] [mcp_server] Deployment\n" in message
    assert "[agent]" not in message
    assert "MCP_MIGRATION_CONFIRMED=1" in message and "dr run deploy" in message
    assert run.call_args.args[0] == [
        "/usr/local/bin/pulumi",
        "stack",
        "export",
        "--stack",
        "dev",
    ]
    # posix_spawn, not fork: forking under Pulumi's gRPC client logs noise.
    assert run.call_args.kwargs["close_fds"] is False


def test_resources_the_stack_only_reads_are_left_out(monkeypatch, check):
    stack_with(monkeypatch, AGENT, OLD_MODEL, OLD_ENVIRONMENT)
    message = check.stop_message()
    assert "  - [my-app] [mcp_server] Custom Model\n" in message
    assert "Execution Environment" not in message
    stack_with(monkeypatch, AGENT, OLD_ENVIRONMENT)  # nothing a deploy would delete
    assert check.stop_message() is None
    pulumi.log.warn.assert_not_called()


def test_lists_ten_resources_then_counts(monkeypatch, check):
    many = [f"{PREFIX}t::[my-app] [mcp_server] Resource {i:02d}" for i in range(13)]
    stack_with(monkeypatch, *many)
    message = check.stop_message()
    assert "Resource 09" in message and "Resource 10" not in message
    assert "  - ...and 3 more" in message


@pytest.mark.parametrize("value", ["1", "true", "YES"])
def test_a_confirmed_deploy_continues_and_says_what_it_deletes(
    monkeypatch, check, value
):
    stack_with(monkeypatch, AGENT, OLD_MODEL)
    monkeypatch.setenv("MCP_MIGRATION_CONFIRMED", value)
    assert check.stop_message() is None
    warning = pulumi.log.warn.call_args.args[0]
    assert warning.startswith("MCP migration: MCP_MIGRATION_CONFIRMED is set")
    assert "  - [my-app] [mcp_server] Custom Model" in warning


def test_once_the_old_server_is_gone_the_confirmation_can_go(monkeypatch, check):
    stack_with(monkeypatch, AGENT)
    monkeypatch.setenv("MCP_MIGRATION_CONFIRMED", "1")
    assert check.stop_message() is None
    pulumi.log.info.assert_called_once_with(check.DONE_MESSAGE)


def test_new_apps_and_migrated_stacks_continue_quietly(monkeypatch, check):
    stack_with(monkeypatch)  # a new stack
    assert check.stop_message() is None
    stack_with(monkeypatch, AGENT)  # the old server is gone
    assert check.stop_message() is None
    pulumi.log.info.assert_not_called()
    pulumi.log.warn.assert_not_called()


def test_an_app_that_kept_the_server_continues(monkeypatch, check):
    run = stack_with(monkeypatch, OLD_MODEL)
    (Path(check.__file__).parent / "mcp_server.py").write_text("")
    assert check.stop_message() is None
    run.assert_not_called()


@pytest.mark.parametrize("failure", ["exit", "not-json", "missing-cli", "no-start"])
def test_an_unreadable_stack_warns_and_continues(monkeypatch, check, failure):
    if failure == "exit":
        stack_with(monkeypatch, OLD_MODEL, returncode=255)
    elif failure == "not-json":
        bad = subprocess.CompletedProcess([], 0, stdout="not json", stderr="")
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=bad))
    elif failure == "missing-cli":
        monkeypatch.setattr(shutil, "which", lambda name: None)
    else:
        monkeypatch.setattr(
            subprocess, "run", MagicMock(side_effect=FileNotFoundError("pulumi"))
        )
    assert check.stop_message() is None
    pulumi.log.warn.assert_called_once_with(
        "MCP migration check skipped: could not read the Pulumi stack."
    )
