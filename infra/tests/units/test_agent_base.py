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
"""Tests for infra.agent_infra.base: shared config used by both runtimes."""

import asyncio
import os
import sys
from collections import namedtuple
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import yaml

# Ensure the test directory is in sys.path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

AGENT_MEMORY_TTL_DAYS = "AGENT_MEMORY_TTL_DAYS"


@pytest.fixture(autouse=True)
def base_mocks(monkeypatch, tmp_path):
    # Python 3.14+ no longer auto-creates an event loop on the main thread,
    # but Pulumi resource registration needs one when infra is first imported.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    monkeypatch.setattr("datarobot_pulumi_utils.pulumi.export", MagicMock())

    mock_use_case = MagicMock()
    mock_use_case.id = "mock-use-case-id"
    monkeypatch.setattr("infra.use_case", mock_use_case)
    monkeypatch.setattr("infra.project_dir", tmp_path)

    mock_llm_module = MagicMock()
    mock_llm_module.custom_model_runtime_parameters = []
    monkeypatch.setitem(sys.modules, "infra.llm", mock_llm_module)

    mock_mcp_module = MagicMock()
    mock_mcp_module.mcp_custom_model_runtime_parameters = []
    monkeypatch.setitem(sys.modules, "infra.mcp_server", mock_mcp_module)

    monkeypatch.setattr("pulumi_datarobot.ExecutionEnvironment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredentialArgs", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.MemorySpace", MagicMock())

    RuntimeParam = namedtuple(
        "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
    )
    monkeypatch.setattr(
        "pulumi_datarobot.CustomModelRuntimeParameterValueArgs", RuntimeParam
    )

    from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments

    patcher = patch.object(
        RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.__class__,
        "id",
        new_callable=PropertyMock,
        return_value="python-311-genai-agents-id",
    )
    patcher.start()

    monkeypatch.setattr("pulumi.export", MagicMock())
    monkeypatch.setattr("pulumi.info", MagicMock())
    monkeypatch.setattr("pulumi.warn", MagicMock())
    monkeypatch.setattr("pulumi.log.error", MagicMock())
    # get_datarobot_url() calls DATAROBOT_ENDPOINT + "/clientConfig/" for real
    # (with a try/except fallback) unless DATAROBOT_WEB_SERVER_URL is set; default
    # to a stub so tests never depend on/hang on outbound network access.
    monkeypatch.setattr(
        "datarobot_pulumi_utils.common.get_datarobot_url",
        lambda: "https://app.datarobot.com/api/v2",
    )

    from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

    _default_ee_version = MagicMock()
    _default_ee_version.id = "69e2134aa5df12076d70afe7"
    _default_ee_version.build_status = (
        EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS.SUCCESS
    )
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=_default_ee_version),
    )

    _mock_output_format = MagicMock()

    class MockOutput:
        def __init__(self, val=None):
            self._val = val

        def apply(self, fn):
            return MockOutput(fn(self._val))

        @classmethod
        def from_input(cls, val):
            return cls(val or "")

        @classmethod
        def all(cls, *outputs):
            combined = cls(None)

            def lazy_apply(fn):
                return cls("output-all-applied")

            combined.apply = lazy_apply  # type: ignore[method-assign]
            return combined

        format = _mock_output_format

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    monkeypatch.setattr("pulumi.Output", MockOutput)

    def create_api_token_credential(*args, **kwargs):
        credential = MagicMock()
        credential.id = MockOutput("mock-credential-id")
        return credential

    monkeypatch.setattr(
        "pulumi_datarobot.ApiTokenCredential", create_api_token_credential
    )

    yield
    patcher.stop()
    loop.close()
    asyncio.set_event_loop(None)


class TestResolveAgentExecutionEnvironment:
    def test_not_set_and_docker_context(self, monkeypatch, tmp_path):
        """No env override, no docker_context.tar.gz -> build from docker_context folder."""
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
        import infra.agent_infra.base as base

        base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
        base.resolve_agent_execution_environment(
            asset_name="[unittest] [agent]",
            application_path=tmp_path,
            use_cases=["customModel", "notebook"],
        )

        base.pulumi.info.assert_any_call(
            "Using docker_context folder to compile the execution environment"
        )
        base.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
        _, kwargs = base.pulumi_datarobot.ExecutionEnvironment.call_args
        assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"
        assert kwargs["programming_language"] == "python"
        assert "docker_context_path" in kwargs
        assert "docker_image" not in kwargs
        assert kwargs["use_cases"] == ["customModel", "notebook"]
        base.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()

    def test_not_set_with_docker_image(self, monkeypatch, tmp_path):
        """No env override, docker_context.tar.gz present -> build from that archive."""
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
        (tmp_path / "docker_context.tar.gz").write_bytes(b"")
        import infra.agent_infra.base as base

        base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
        base.resolve_agent_execution_environment(
            asset_name="[unittest] [agent]",
            application_path=tmp_path,
            use_cases=["customModel"],
        )

        base.pulumi.info.assert_any_call(
            "Using prebuilt Dockerfile docker_context.tar.gz to run the execution environment"
        )
        _, kwargs = base.pulumi_datarobot.ExecutionEnvironment.call_args
        assert "docker_image" in kwargs
        assert "docker_context_path" not in kwargs
        assert kwargs["use_cases"] == ["customModel"]
        base.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()

    def test_default_env_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT",
            "[DataRobot] Python 3.11 GenAI Agents",
        )
        import infra.agent_infra.base as base

        base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
        base.resolve_agent_execution_environment(
            asset_name="[unittest] [agent]",
            application_path=tmp_path,
            use_cases=["customModel", "notebook"],
        )

        base.pulumi.info.assert_any_call(
            "Using default GenAI Agentic Execution Environment."
        )
        base.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
        _, kwargs = base.pulumi_datarobot.ExecutionEnvironment.get.call_args
        assert kwargs["id"] == "python-311-genai-agents-id"
        assert kwargs["version_id"] is None
        base.pulumi_datarobot.ExecutionEnvironment.assert_not_called()

    def test_default_env_pinned(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT",
            "[DataRobot] Python 3.11 GenAI Agents",
        )
        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
            "6a4e0e5874d3a4076d933c72",
        )
        import infra.agent_infra.base as base

        base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
        base.resolve_agent_execution_environment(
            asset_name="[unittest] [agent]",
            application_path=tmp_path,
            use_cases=["customModel"],
        )

        _, kwargs = base.pulumi_datarobot.ExecutionEnvironment.get.call_args
        assert kwargs["id"] == "python-311-genai-agents-id"
        assert kwargs["version_id"] == "69e2134aa5df12076d70afe7"

    def test_custom_env_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", "Custom Execution Environment"
        )
        import infra.agent_infra.base as base

        base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
        base.resolve_agent_execution_environment(
            asset_name="[unittest] [agent]",
            application_path=tmp_path,
            use_cases=["customModel"],
        )

        _, kwargs = base.pulumi_datarobot.ExecutionEnvironment.get.call_args
        assert kwargs["id"] == "Custom Execution Environment"
        assert kwargs["version_id"] is None
        base.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_reset_environment_between_tests(monkeypatch, tmp_path):
    """Guard that execution-environment env vars don't leak between tests.

    Ported from the pre-split suite, where it reloaded the whole monolith. The
    equivalent here is base's resolver: with no override set it must build a new
    execution environment rather than look one up.
    """
    assert os.environ.get("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT") is None

    import infra.agent_infra.base as base

    base.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    base.resolve_agent_execution_environment(
        asset_name="[unittest] [agent]",
        application_path=tmp_path,
        use_cases=["customModel", "notebook"],
    )

    base.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    base.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


class TestResolveExecutionEnvironmentVersion:
    def test_not_found_returns_none(self, monkeypatch):
        from datarobot.errors import ClientError

        import infra.agent_infra.base as base

        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
            "6a4e0e5874d3a4076d933c72",
        )
        monkeypatch.setattr(
            "datarobot.ExecutionEnvironmentVersion.get",
            MagicMock(side_effect=ClientError("Version not found", 404)),
        )

        version_id = base.resolve_execution_environment_version(
            "ee-base-id", "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID"
        )

        assert version_id is None
        base.pulumi.warn.assert_called_once()
        assert "6a4e0e5874d3a4076d933c72" in base.pulumi.warn.call_args[0][0]

    def test_found(self, monkeypatch):
        from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

        import infra.agent_infra.base as base

        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
            "6a4e0e5874d3a4076d933c72",
        )
        mock_version = MagicMock()
        mock_version.id = "6a4e0e5874d3a4076d933c72"
        mock_version.build_status = EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS.SUCCESS
        monkeypatch.setattr(
            "datarobot.ExecutionEnvironmentVersion.get",
            MagicMock(return_value=mock_version),
        )

        version_id = base.resolve_execution_environment_version(
            "ee-base-id", "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID"
        )

        assert version_id == "6a4e0e5874d3a4076d933c72"
        base.pulumi.warn.assert_not_called()

    def test_not_success_returns_none(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
            "6a4e0e5874d3a4076d933c72",
        )
        mock_version = MagicMock()
        mock_version.id = "6a4e0e5874d3a4076d933c72"
        mock_version.build_status = "processing"
        monkeypatch.setattr(
            "datarobot.ExecutionEnvironmentVersion.get",
            MagicMock(return_value=mock_version),
        )

        version_id = base.resolve_execution_environment_version(
            "ee-base-id", "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID"
        )

        assert version_id is None
        base.pulumi.warn.assert_called_once()

    def test_unset_returns_none(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.delenv(
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID", raising=False
        )
        mock_get = MagicMock()
        monkeypatch.setattr("datarobot.ExecutionEnvironmentVersion.get", mock_get)

        version_id = base.resolve_execution_environment_version(
            "ee-base-id", "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID"
        )

        assert version_id is None
        mock_get.assert_not_called()
        base.pulumi.warn.assert_not_called()


class TestMaybeImportFromModule:
    def test_empty_module_name_returns_none(self):
        import infra.agent_infra.base as base

        assert base.maybe_import_from_module("", "anything") is None

    def test_resolves_against_top_level_infra_package(self):
        """The co-deployed module lives at infra/<name>.py, a sibling of
        infra.agent_infra -- not inside it (see base.py's docstring note)."""
        import infra.agent_infra.base as base

        assert base._TOP_LEVEL_INFRA_PACKAGE == "infra"

    def test_returns_object_when_present(self, monkeypatch):
        import importlib

        import infra.agent_infra.base as base

        module = MagicMock()
        module.some_export = ["value"]
        real_import_module = importlib.import_module

        def fake_import_module(name, package=None):
            if name == ".sibling" and package == "infra":
                return module
            return real_import_module(name, package)

        monkeypatch.setattr(importlib, "import_module", fake_import_module)
        assert base.maybe_import_from_module("sibling", "some_export") == ["value"]

    def test_absent_module_returns_none(self, monkeypatch):
        import importlib

        import infra.agent_infra.base as base

        real_import_module = importlib.import_module

        def fake_import_module(name, package=None):
            if name == ".absent":
                raise ModuleNotFoundError("no module named absent")
            return real_import_module(name, package)

        monkeypatch.setattr(importlib, "import_module", fake_import_module)
        assert base.maybe_import_from_module("absent", "x") is None

    def test_unexpected_error_propagates(self, monkeypatch):
        import importlib

        import infra.agent_infra.base as base

        real_import_module = importlib.import_module

        def fake_import_module(name, package=None):
            if name == ".broken":
                raise RuntimeError("boom")
            return real_import_module(name, package)

        monkeypatch.setattr(importlib, "import_module", fake_import_module)
        with pytest.raises(RuntimeError, match="boom"):
            base.maybe_import_from_module("broken", "x")


class TestGetMcpCustomModelRuntimeParameters:
    def test_from_module(self, monkeypatch):
        import infra.agent_infra.base as base

        sentinel = ["mcp-runtime-param-sentinel"]
        calls = {}

        def fake_maybe_import(module, object_name):
            calls["module"] = module
            calls["object_name"] = object_name
            return sentinel

        monkeypatch.setattr(base, "maybe_import_from_module", fake_maybe_import)
        assert base.get_mcp_custom_model_runtime_parameters() == sentinel
        assert calls["module"] == base.MCP_MODULE_NAME == "mcp_server"
        assert calls["object_name"] == "mcp_custom_model_runtime_parameters"

    def test_present_but_empty_module_does_not_fall_back_to_env(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv("MCP_DEPLOYMENT_ID", "stale-deployment-id")
        monkeypatch.setattr(base, "maybe_import_from_module", lambda m, o: [])
        assert base.get_mcp_custom_model_runtime_parameters() == []

    def test_fallback_to_env(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv("MCP_DEPLOYMENT_ID", "test-deployment-123")
        monkeypatch.setenv("EXTERNAL_MCP_URL", "https://example.com/mcp")
        monkeypatch.setenv(
            "EXTERNAL_MCP_HEADERS", '{"Authorization": "Bearer token123"}'
        )
        monkeypatch.setenv("EXTERNAL_MCP_TRANSPORT", "sse")
        monkeypatch.setattr(base, "maybe_import_from_module", lambda m, o: None)

        result = base.get_mcp_custom_model_runtime_parameters()

        assert len(result) == 4
        by_key = {p.key: p for p in result}
        assert by_key["MCP_DEPLOYMENT_ID"].value == "test-deployment-123"
        assert by_key["EXTERNAL_MCP_URL"].value == "https://example.com/mcp"
        assert (
            by_key["EXTERNAL_MCP_HEADERS"].value
            == '{"Authorization": "Bearer token123"}'
        )
        assert by_key["EXTERNAL_MCP_TRANSPORT"].value == "sse"


# --- A2A workflow.yaml helpers ----------------------------------------------
#
# Everything below reads the agent's workflow.yaml through `base`. The config is
# built as a dict and serialized by yaml, so each test reads as the setting under
# test rather than as hand-indented YAML embedded in a string literal.

#: A front end with no `a2a` block at all.
WORKFLOW_WITHOUT_A2A = {"general": {"front_end": {"streaming": True}}}


def _workflow_with_a2a(**a2a_fields):
    """workflow.yaml config whose ``general.front_end.a2a`` block carries ``a2a_fields``."""
    return {
        "general": {"front_end": {"a2a": {"server": {"name": "test"}, **a2a_fields}}}
    }


def _write_workflow_yaml(monkeypatch, tmp_path, config, *, in_agent_subdir=False):
    """Point ``base.project_dir`` at a tmp agent whose workflow.yaml holds ``config``.

    ``in_agent_subdir`` writes it to ``agent/agent/`` instead of the
    agent root, exercising ``_find_workflow_yaml``'s fallback location.
    """
    import infra.agent_infra.base as base

    agent_dir = tmp_path / "agent"
    if in_agent_subdir:
        agent_dir = agent_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "workflow.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setattr(base, "project_dir", tmp_path / "infra")


def _without_workflow_yaml(monkeypatch, tmp_path):
    """Point ``base.project_dir`` at a tmp dir holding no workflow.yaml at all."""
    import infra.agent_infra.base as base

    monkeypatch.setattr(base, "project_dir", tmp_path / "infra")


def _collect_pulumi_warnings(monkeypatch):
    """Capture ``pulumi.warn`` messages emitted from this point on."""
    import infra.agent_infra.base as base

    messages: list[str] = []
    monkeypatch.setattr(base.pulumi, "warn", messages.append)
    return messages


class TestCheckA2aServerEnabled:
    def test_true_when_workflow_yaml_has_a2a(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(monkeypatch, tmp_path, _workflow_with_a2a())
        assert base.check_a2a_server_enabled() is True

    def test_true_when_workflow_yaml_in_agent_subdir(self, monkeypatch, tmp_path):
        """workflow.yaml under agent/ (fallback) is checked when the root copy is absent."""
        import infra.agent_infra.base as base

        _write_workflow_yaml(
            monkeypatch, tmp_path, _workflow_with_a2a(), in_agent_subdir=True
        )
        assert base.check_a2a_server_enabled() is True

    def test_false_when_no_a2a_key(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(monkeypatch, tmp_path, WORKFLOW_WITHOUT_A2A)
        assert base.check_a2a_server_enabled() is False

    def test_false_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _without_workflow_yaml(monkeypatch, tmp_path)
        assert base.check_a2a_server_enabled() is False


class TestCheckA2aUnauthenticatedWellKnownRouteEnabled:
    def test_true_when_flag_set_in_workflow_yaml(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(
            monkeypatch,
            tmp_path,
            _workflow_with_a2a(enable_unauthenticated_well_known_route=True),
        )
        assert base.check_a2a_unauthenticated_well_known_route_enabled() is True

    def test_false_when_flag_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(monkeypatch, tmp_path, _workflow_with_a2a())
        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False

    def test_false_when_flag_explicitly_false(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(
            monkeypatch,
            tmp_path,
            _workflow_with_a2a(enable_unauthenticated_well_known_route=False),
        )
        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False

    def test_false_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _without_workflow_yaml(monkeypatch, tmp_path)
        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False


class TestGetA2aMountPath:
    """`a2a.mount_path` drives every A2A URL and route infra emits.

    datarobot-genai mounts the A2A app at `/{mount_path}`, so a value read wrong here
    produces URLs that resolve nowhere -- and, on the workload runtime, an
    unauthenticated agent-card route attached to a dead path that 404s silently.
    """

    def _resolve(self, monkeypatch, tmp_path, **a2a_fields) -> str:
        """Mount path resolved from an ``a2a`` block carrying ``a2a_fields``."""
        import infra.agent_infra.base as base

        _write_workflow_yaml(monkeypatch, tmp_path, _workflow_with_a2a(**a2a_fields))
        return base.get_a2a_mount_path()

    def test_default_when_a2a_block_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _write_workflow_yaml(monkeypatch, tmp_path, WORKFLOW_WITHOUT_A2A)
        assert base.get_a2a_mount_path() == "a2a"

    def test_default_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        _without_workflow_yaml(monkeypatch, tmp_path)
        assert base.get_a2a_mount_path() == "a2a"

    def test_default_when_mount_path_absent(self, monkeypatch, tmp_path):
        assert self._resolve(monkeypatch, tmp_path) == "a2a"

    def test_custom_value(self, monkeypatch, tmp_path):
        assert (
            self._resolve(monkeypatch, tmp_path, mount_path="custom-a2a-mount-path")
            == "custom-a2a-mount-path"
        )

    def test_surrounding_slashes_stripped(self, monkeypatch, tmp_path):
        """`"/a2a/"` and `"a2a"` are equivalent, matching datarobot-genai's normalization."""
        assert (
            self._resolve(monkeypatch, tmp_path, mount_path="/custom-a2a-mount-path/")
            == "custom-a2a-mount-path"
        )

    def test_interior_slashes_kept_for_multi_segment_mount(self, monkeypatch, tmp_path):
        assert self._resolve(monkeypatch, tmp_path, mount_path="api/a2a") == "api/a2a"

    def test_blank_falls_back_to_default_with_warning(self, monkeypatch, tmp_path):
        """Empty is rejected by datarobot-genai at startup; infra warns but does not raise."""
        warnings = _collect_pulumi_warnings(monkeypatch)

        assert self._resolve(monkeypatch, tmp_path, mount_path="/") == "a2a"
        assert len(warnings) == 1
        assert "empty" in warnings[0]

    def test_invalid_segment_warns_but_passes_through(self, monkeypatch, tmp_path):
        """The container is the authoritative validator, so infra must not block the deploy."""
        warnings = _collect_pulumi_warnings(monkeypatch)

        assert self._resolve(monkeypatch, tmp_path, mount_path="bad path") == "bad path"
        assert len(warnings) == 1
        assert "bad path" in warnings[0]

    def test_dot_leading_segment_warns_but_passes_through(self, monkeypatch, tmp_path):
        warnings = _collect_pulumi_warnings(monkeypatch)

        assert (
            self._resolve(monkeypatch, tmp_path, mount_path=".well-known")
            == ".well-known"
        )
        assert len(warnings) == 1

    def test_valid_value_does_not_warn(self, monkeypatch, tmp_path):
        warnings = _collect_pulumi_warnings(monkeypatch)

        assert self._resolve(monkeypatch, tmp_path, mount_path="api/a2a") == "api/a2a"
        assert warnings == []


class TestA2aUrl:
    def test_appends_mount_path_with_single_trailing_slash(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "A2A_MOUNT_PATH", "a2a")
        assert (
            base.a2a_url("https://example.com/deployments/abc/directAccess")
            == "https://example.com/deployments/abc/directAccess/a2a/"
        )

    def test_follows_custom_mount_path(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "A2A_MOUNT_PATH", "custom-a2a-mount-path")
        assert (
            base.a2a_url("https://example.com/deployments/abc/directAccess")
            == "https://example.com/deployments/abc/directAccess/custom-a2a-mount-path/"
        )

    def test_collapses_trailing_slash_on_base(self, monkeypatch):
        """Workload endpoints arrive with a trailing slash; the join must not double it."""
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "A2A_MOUNT_PATH", "a2a")
        assert base.a2a_url("https://workload.example.com/") == (
            "https://workload.example.com/a2a/"
        )

    def test_multi_segment_mount_path(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "A2A_MOUNT_PATH", "api/a2a")
        assert base.a2a_url("https://workload.example.com") == (
            "https://workload.example.com/api/a2a/"
        )


class TestBuildSharedAgentRuntimeParameters:
    def test_always_includes_gunicorn_timeout(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.delenv("SESSION_SECRET_KEY", raising=False)
        params = base.build_shared_agent_runtime_parameters()
        timeout_param = next(
            p for p in params if p.key == "AGENT_GUNICORN_WORKER_TIMEOUT"
        )
        assert timeout_param.type == "string"
        assert timeout_param.value == "600"

    def test_includes_llm_and_mcp_params(self, monkeypatch):
        import infra.agent_infra.base as base

        RuntimeParam = base.pulumi_datarobot.CustomModelRuntimeParameterValueArgs
        monkeypatch.setattr(
            base,
            "llm_custom_model_runtime_parameters",
            [RuntimeParam(key="LLM_DEPLOYMENT_ID", type="string", value="dep-1")],
        )
        monkeypatch.setattr(base, "get_mcp_custom_model_runtime_parameters", lambda: [])
        params = base.build_shared_agent_runtime_parameters()
        assert any(p.key == "LLM_DEPLOYMENT_ID" for p in params)

    def test_session_secret_key_becomes_credential(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv("SESSION_SECRET_KEY", "secret_value")
        params = base.build_shared_agent_runtime_parameters()
        session_param = next(p for p in params if p.key == "SESSION_SECRET_KEY")
        assert session_param.type == "credential"
        assert session_param.value is not None
        base.pulumi.export.assert_any_call("SESSION_SECRET_KEY", "secret_value")

    def test_session_secret_key_absent_when_unset(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.delenv("SESSION_SECRET_KEY", raising=False)
        params = base.build_shared_agent_runtime_parameters()
        assert not any(p.key == "SESSION_SECRET_KEY" for p in params)

    def test_idp_agent_id_included_when_set(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv("IDP_AGENT_ID", "idp-agent-123")
        params = base.build_shared_agent_runtime_parameters()
        idp_param = next(p for p in params if p.key == "IDP_AGENT_ID")
        assert idp_param.type == "string"
        assert idp_param.value == "idp-agent-123"

    def test_private_jwk_becomes_credential(self, monkeypatch):
        import infra.agent_infra.base as base

        monkeypatch.setenv("IDP_AGENT_PRIVATE_KEY_JWK", '{"kty": "RSA"}')
        params = base.build_shared_agent_runtime_parameters()
        jwk_param = next(p for p in params if p.key == "IDP_AGENT_PRIVATE_KEY_JWK")
        assert jwk_param.type == "credential"
        assert jwk_param.value is not None

    def test_excludes_custom_model_workers(self, monkeypatch):
        """CUSTOM_MODEL_WORKERS has no Workload-container equivalent; only deployment.py adds it."""
        import infra.agent_infra.base as base

        params = base.build_shared_agent_runtime_parameters()
        assert not any(p.key == "CUSTOM_MODEL_WORKERS" for p in params)

    def test_memory_ttl_excluded_when_memory_disabled(self, monkeypatch):
        """With memory off the TTL parameter is absent, even if the env var is set."""
        import importlib

        import infra.agent_infra.base as base

        monkeypatch.setenv(AGENT_MEMORY_TTL_DAYS, "1")
        importlib.reload(base)

        params = base.build_shared_agent_runtime_parameters()
        assert not any(p.key == AGENT_MEMORY_TTL_DAYS for p in params)


class TestEnableAgentHAMode:
    """ENABLE_AGENT_HA_MODE is read once at base's import time; reload to re-parse."""

    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_AGENT_HA_MODE", raising=False)
        import importlib

        import infra.agent_infra.base as base

        importlib.reload(base)
        assert base.ENABLE_AGENT_HA_MODE is False

    def test_disabled_explicit_false(self, monkeypatch):
        """'false' is disabled, same as unset -- only 'true' enables HA."""
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "false")
        import importlib

        import infra.agent_infra.base as base

        importlib.reload(base)
        assert base.ENABLE_AGENT_HA_MODE is False

    def test_enabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "true")
        import importlib

        import infra.agent_infra.base as base

        importlib.reload(base)
        assert base.ENABLE_AGENT_HA_MODE is True

    def test_case_insensitive_true_only(self, monkeypatch):
        import importlib

        import infra.agent_infra.base as base

        for value, expected in [
            ("True", True),
            ("TRUE", True),
            ("1", False),
            ("yes", False),
        ]:
            monkeypatch.setenv("ENABLE_AGENT_HA_MODE", value)
            importlib.reload(base)
            assert base.ENABLE_AGENT_HA_MODE is expected
