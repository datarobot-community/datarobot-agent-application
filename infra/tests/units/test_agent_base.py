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


class TestCheckA2aServerEnabled:
    def test_true_when_workflow_yaml_has_a2a(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    a2a:\n      server:\n        name: test\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_server_enabled() is True

    def test_true_when_workflow_yaml_in_agent_subdir(self, monkeypatch, tmp_path):
        """workflow.yaml under agent/ (fallback) is checked when the root copy is absent."""
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    a2a:\n      server:\n        name: test\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_server_enabled() is True

    def test_false_when_no_a2a_key(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    streaming: true\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_server_enabled() is False

    def test_false_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")
        assert base.check_a2a_server_enabled() is False


class TestCheckA2aRemoteClientEnabled:
    def test_true_when_workflow_yaml_has_authenticated_a2a_client(
        self, monkeypatch, tmp_path
    ):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "function_groups:\n"
            "  remote_agent:\n"
            "    _type: authenticated_a2a_client\n"
            "    url: https://app.datarobot.com/api/v2/deployments/abc/directAccess/a2a/\n"
            "    auth_provider: datarobot_auth\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base._check_a2a_remote_client_enabled() is True

    def test_false_when_no_remote_a2a_client(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    streaming: true\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base._check_a2a_remote_client_enabled() is False

    def test_false_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")
        assert base._check_a2a_remote_client_enabled() is False


class TestCheckA2aUnauthenticatedWellKnownRouteEnabled:
    def test_true_when_flag_set_in_workflow_yaml(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    a2a:\n"
            "      enable_unauthenticated_well_known_route: true\n"
            "      server:\n        name: test\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_unauthenticated_well_known_route_enabled() is True

    def test_false_when_flag_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    a2a:\n      server:\n        name: test\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False

    def test_false_when_flag_explicitly_false(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        agent_dir = tmp_path / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "workflow.yaml").write_text(
            "general:\n  front_end:\n    a2a:\n"
            "      enable_unauthenticated_well_known_route: false\n"
            "      server:\n        name: test\n"
        )
        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")

        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False

    def test_false_when_workflow_yaml_absent(self, monkeypatch, tmp_path):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "project_dir", tmp_path / "infra")
        assert base.check_a2a_unauthenticated_well_known_route_enabled() is False


class TestRegistryCacheMemorySpace:
    """Provision AGENT_CARD_REGISTRY_MEMORY_SPACE_ID when remote A2A clients are configured."""

    def test_registry_cache_space_param_included_when_remote_a2a_enabled(
        self, monkeypatch
    ):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "IS_A2A_REMOTE_CLIENT_ENABLED", True)
        params = base.build_shared_agent_runtime_parameters()
        space_param = next(
            p for p in params if p.key == base.AGENT_CARD_REGISTRY_MEMORY_SPACE_ID
        )
        assert space_param.type == "string"
        assert space_param.value is not None
        base.pulumi_datarobot.MemorySpace.assert_any_call(
            base.agent_asset_name + " Agent Card Registry Cache",
        )

    def test_registry_cache_space_param_absent_when_remote_a2a_disabled(
        self, monkeypatch
    ):
        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "IS_A2A_REMOTE_CLIENT_ENABLED", False)
        params = base.build_shared_agent_runtime_parameters()
        assert not any(
            p.key == base.AGENT_CARD_REGISTRY_MEMORY_SPACE_ID for p in params
        )

    def test_registry_cache_space_id_disk_export(self, monkeypatch):
        from unittest.mock import ANY, MagicMock

        import infra.agent_infra.base as base

        monkeypatch.setattr(base, "IS_A2A_REMOTE_CLIENT_ENABLED", True)
        monkeypatch.setattr(base, "export", MagicMock())
        base.build_shared_agent_runtime_parameters()

        base.export.assert_any_call(
            base.AGENT_CARD_REGISTRY_MEMORY_SPACE_ID,
            ANY,
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
