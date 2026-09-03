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
import os
import sys
from collections import namedtuple
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from dev_tools.lineage.pulumi_managers import (
    MCPPromptMetadataPulumiManager,
    MCPResourceMetadataPulumiManager,
    MCPToolMetadataPulumiManager,
)

# Ensure the units test directory is in sys.path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# Patch all Pulumi resources and functions used in the module
@pytest.fixture(autouse=True)
def pulumi_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    # These tests exercise datarobot-serverless provisioning; override host .env.
    monkeypatch.setenv("MCP_DEPLOYMENT_TYPE", "datarobot-serverless")
    monkeypatch.delenv("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.delenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID", raising=False
    )
    monkeypatch.delenv("DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT", raising=False)
    monkeypatch.setattr("datarobot_pulumi_utils.pulumi.export", MagicMock())
    # Mock infra.__init__ exported objects
    mock_use_case = MagicMock()
    mock_use_case.id = "mock-use-case-id"
    mock_project_dir = tmp_path
    monkeypatch.setattr("infra.use_case", mock_use_case)
    monkeypatch.setattr("infra.project_dir", mock_project_dir)

    # Create the mcp app directory structure expected by module-level code.
    # mcp_execution_environment binds project_dir at its own import, so patch the
    # submodule's global too — otherwise the docker-context check (and the tests'
    # stub files) would run against the real rendered app directory.
    monkeypatch.setattr(
        "infra.mcp_server_infra.mcp_execution_environment.project_dir",
        mock_project_dir,
    )
    mcp_app_dir = tmp_path.parent / "mcp_server"
    mcp_app_dir.mkdir(exist_ok=True)
    docker_build_files = {
        "Dockerfile": "FROM scratch\n",
        "pyproject.toml": "",
        "uv.lock": "",
        "start_server.sh": "#!/bin/sh\n",
    }
    for filename, content in docker_build_files.items():
        (mcp_app_dir / filename).write_text(content, encoding="utf-8")

    # Mock user params module
    mock_user_params_module = MagicMock()
    mock_user_params_module.MCP_USER_RUNTIME_PARAMETERS = []
    monkeypatch.setitem(
        sys.modules,
        "infra.mcp_server_user_params",
        mock_user_params_module,
    )

    # Mock pulumi_datarobot resources
    monkeypatch.setattr("pulumi_datarobot.ExecutionEnvironment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.CustomModel", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.RegisteredModel", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.PredictionEnvironment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.Deployment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredential", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredentialArgs", MagicMock())

    # Mock CustomModelRuntimeParameterValueArgs to return simple namedtuple objects
    RuntimeParam = namedtuple(
        "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
    )
    monkeypatch.setattr(
        "pulumi_datarobot.CustomModelRuntimeParameterValueArgs", RuntimeParam
    )
    monkeypatch.setattr("pulumi_datarobot.CustomModelTagArgs", MagicMock())

    # Patch the id property of the RuntimeEnvironment instance for PYTHON_311_GENAI_AGENTS
    from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments

    patcher = patch.object(
        RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.__class__,
        "id",
        new_callable=PropertyMock,
        return_value="python-311-genai-agents-id",
    )
    patcher.start()

    # Mock pulumi functions
    monkeypatch.setattr("pulumi.export", MagicMock())
    monkeypatch.setattr("pulumi.info", MagicMock())
    monkeypatch.setattr("pulumi.warn", MagicMock())
    monkeypatch.setattr("pulumi.log.error", MagicMock())

    # Mock datarobot.ExecutionEnvironmentVersion.get to return a successful version by default
    from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

    _default_ee_version = MagicMock()
    _default_ee_version.id = "690cd2f698419673f938f7c4"
    _default_ee_version.build_status = (
        EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS.SUCCESS
    )
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=_default_ee_version),
    )

    # Mock Output to behave like a Pulumi Output with .apply() / .secret().
    # Use __init__ (not __new__) so MagicMock finishes setup before setattr;
    # otherwise SESSION_SECRET_KEY → Output.secret() raises AttributeError: _mock_methods.
    class MockOutput(MagicMock):
        def __init__(self, val=None, *args, **kwargs):
            # Do not pass val to MagicMock — it would be treated as `spec`.
            super().__init__(*args, **kwargs)
            self.apply = MagicMock(side_effect=lambda fn, v=val: fn(v))

        @classmethod
        def __class_getitem__(cls, item):
            return cls

        @classmethod
        def secret(cls, val):
            return cls(val)

    MockOutput.from_input = MagicMock(side_effect=lambda val: MockOutput(val))
    MockOutput.format = MagicMock()
    monkeypatch.setattr("pulumi.Output", MockOutput)

    # Mock MCP metadata related module
    monkeypatch.setattr(MCPToolMetadataPulumiManager, "load_metadata", Mock())
    monkeypatch.setattr(MCPToolMetadataPulumiManager, "create_pulumi_resources", Mock())
    monkeypatch.setattr(
        MCPToolMetadataPulumiManager, "export_summary_to_pulumi_stack", Mock()
    )
    monkeypatch.setattr(MCPPromptMetadataPulumiManager, "load_metadata", Mock())
    monkeypatch.setattr(
        MCPPromptMetadataPulumiManager, "create_pulumi_resources", Mock()
    )
    monkeypatch.setattr(
        MCPPromptMetadataPulumiManager, "export_summary_to_pulumi_stack", Mock()
    )
    monkeypatch.setattr(MCPResourceMetadataPulumiManager, "load_metadata", Mock())
    monkeypatch.setattr(
        MCPResourceMetadataPulumiManager, "create_pulumi_resources", Mock()
    )
    monkeypatch.setattr(
        MCPResourceMetadataPulumiManager, "export_summary_to_pulumi_stack", Mock()
    )

    yield
    patcher.stop()


def test_execution_environment_not_set_uses_app_root(monkeypatch):
    """Test execution environment creation when DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT is not set."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", raising=False)

    import importlib

    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    mcp_infra.pulumi.info.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using app directory as Docker build context for execution environment"
    )

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    _args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.call_args

    assert kwargs["programming_language"] == "python"
    assert "docker_context_path" in kwargs
    assert kwargs["opts"].retain_on_delete is False
    assert getattr(kwargs["opts"], "import_", None) is None

    # ExecutionEnvironment.get should not be called when env var is not set
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


def test_execution_environment_name_override_imports_existing(monkeypatch):
    """Shared CI EE names import an existing DataRobot id instead of creating duplicates."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.setenv(
        "DATAROBOT_MCP_EXECUTION_ENVIRONMENT_NAME",
        "ci-e2e-mcp-server-docker-ee",
    )

    existing = MagicMock()
    existing.id = "ee-existing-id"
    existing.name = "ci-e2e-mcp-server-docker-ee"
    existing.created = "2026-08-27T00:00:00Z"
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironment.list",
        MagicMock(return_value=[existing]),
    )

    import importlib

    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    mcp_infra.pulumi.info.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    _args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.call_args
    assert kwargs["name"] == "ci-e2e-mcp-server-docker-ee"
    assert kwargs["opts"].import_ == "ee-existing-id"
    assert kwargs["opts"].retain_on_delete is True
    mcp_infra.pulumi.info.assert_any_call(
        "Importing existing execution environment: ee-existing-id (shared name ci-e2e-mcp-server-docker-ee)"
    )


def test_execution_environment_default_set(monkeypatch):
    """Test execution environment when DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT is set to default value."""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT",
        "[DataRobot] Python 3.11 GenAI Agents",
    )

    import importlib

    import infra.mcp_server as mcp_infra

    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using default GenAI Agentic Execution Environment."
    )

    # Check that ExecutionEnvironment.get was called with the correct parameters
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    _args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "python-311-genai-agents-id"
    assert kwargs["version_id"] is None

    # ExecutionEnvironment constructor should not be called when using default env
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_execution_environment_pinned_set(monkeypatch):
    """Test execution environment when pinned version ID is set."""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT",
        "[DataRobot] Python 3.11 GenAI Agents",
    )
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
        "690cd2f698419673f938f7c4",
    )

    import importlib

    import infra.mcp_server as mcp_infra

    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using default GenAI Agentic Execution Environment."
    )
    mcp_infra.pulumi.info.assert_any_call(
        "Using existing execution environment: python-311-genai-agents-id"
        " Version ID: 690cd2f698419673f938f7c4"
    )

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    _args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "python-311-genai-agents-id"
    assert kwargs["version_id"] == "690cd2f698419673f938f7c4"

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_execution_environment_custom_set(monkeypatch):
    """Test execution environment when DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT is set to a custom value."""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", "Custom Execution Environment"
    )

    import importlib

    import infra.mcp_server as mcp_infra

    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using existing execution environment: Custom Execution Environment"
        " Version ID: None"
    )

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    _args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "Custom Execution Environment"
    assert kwargs["version_id"] is None

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_resolve_execution_environment_version_not_found_returns_none(monkeypatch):
    """When pinned EE version is not found in DataRobot, warn and return None (use latest)."""
    from datarobot.errors import ClientError

    import infra.mcp_server as mcp_infra

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
        "a1b2c3d4e5f6071829364455",
    )
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(side_effect=ClientError("Version not found", 404)),
    )

    version_id = mcp_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    mcp_infra.pulumi.warn.assert_called_once()
    call_msg = mcp_infra.pulumi.warn.call_args[0][0]
    assert "a1b2c3d4e5f6071829364455" in call_msg
    assert "using latest" in call_msg


def test_resolve_execution_environment_version_found(monkeypatch):
    """When pinned version exists and build_status is SUCCESS, return its id."""
    from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

    import infra.mcp_server as mcp_infra

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
        "abcdef0123456789abcdef01",
    )
    mock_version = MagicMock()
    mock_version.id = "abcdef0123456789abcdef01"
    mock_version.build_status = EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS.SUCCESS
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=mock_version),
    )

    version_id = mcp_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id == "abcdef0123456789abcdef01"
    mcp_infra.pulumi.warn.assert_not_called()


def test_resolve_execution_environment_version_not_success_returns_none(monkeypatch):
    """When get() succeeds but build_status is not SUCCESS, return None with a warning."""
    import infra.mcp_server as mcp_infra

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
        "abcdef0123456789abcdef01",
    )
    mock_version = MagicMock()
    mock_version.id = "abcdef0123456789abcdef01"
    mock_version.build_status = "processing"
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=mock_version),
    )

    version_id = mcp_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    mcp_infra.pulumi.warn.assert_called_once()
    call_msg = mcp_infra.pulumi.warn.call_args[0][0]
    assert "abcdef0123456789abcdef01" in call_msg
    assert "using latest" in call_msg


def test_resolve_execution_environment_version_unset_returns_none(monkeypatch):
    """When env var is unset or invalid, return None without calling DR API."""
    import infra.mcp_server as mcp_infra

    monkeypatch.delenv(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID", raising=False
    )
    mock_get = MagicMock()
    monkeypatch.setattr("datarobot.ExecutionEnvironmentVersion.get", mock_get)

    version_id = mcp_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    mock_get.assert_not_called()
    mcp_infra.pulumi.warn.assert_not_called()


def test_reset_environment_between_tests():
    """Test to ensure that environment variables don't leak between tests."""
    assert os.environ.get("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT") is None

    import importlib

    import infra.mcp_server as mcp_infra

    importlib.reload(mcp_infra)

    # Default behavior should be to create a new execution environment
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


class TestGetDeploymentsAppFiles:
    def test_get_deployments_app_files_collects_app_python_files(
        self, tmp_path
    ) -> None:
        import infra.mcp_server as mcp_infra

        app_root = tmp_path.parent / "mcp_server"
        app_dir = app_root / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "main.py").write_text("print('hi')\n", encoding="utf-8")
        actual = {name for _, name in mcp_infra.get_deployments_app_files()}
        # The pulumi_mocks fixture stubs the essential root files in app_root,
        # mirroring a real rendered app where they always exist.
        expected = {"app/main.py", "pyproject.toml", "uv.lock", "start_server.sh"}
        assert actual == expected

    def test_get_deployments_app_files_excludes_test_paths(self, tmp_path) -> None:
        import infra.mcp_server as mcp_infra

        app_root = tmp_path.parent / "mcp_server"
        tests_dir = app_root / "tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_x.py").write_text("pass\n", encoding="utf-8")
        actual = {name for _, name in mcp_infra.get_deployments_app_files()}
        expected = "tests/test_x.py"
        assert expected not in actual


class TestMcpDeploymentType:
    def test_mcp_deployment_type_warns_when_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("MCP_DEPLOYMENT_TYPE", raising=False)
        import importlib

        import infra.mcp_server as mcp_infra

        warn_mock = cast(MagicMock, mcp_infra.pulumi.warn)
        warn_mock.reset_mock()
        importlib.reload(mcp_infra)
        actual = any(
            "MCP_DEPLOYMENT_TYPE not set" in str(call.args[0])
            for call in warn_mock.call_args_list
        )
        expected = True
        assert actual == expected

    def test_mcp_deployment_type_routes_to_workload_image_uri(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("MCP_DEPLOYMENT_TYPE", "datarobot-workload-preview")
        monkeypatch.setenv("MCP_WORKLOAD_IMAGE_URI", "img:tag")
        import importlib

        import infra.mcp_server as mcp_infra

        return_value: dict[str, Any] = {
            "execution_environment": None,
            "deployment": None,
            "mcp_server_mcp_endpoint": "ep",
            "mcp_server_base_endpoint": "base",
            "mcp_custom_model_runtime_parameters": [],
        }
        with patch(
            "infra.mcp_server_infra.workload.provision_workload_mcp_server_from_image_uri",
            return_value=return_value,
        ) as mock_from_image:
            importlib.reload(mcp_infra)
            actual = mock_from_image.call_args.kwargs["workload_image_uri"]
            expected = "img:tag"
            assert actual == expected

    def test_mcp_deployment_type_routes_to_workload_build(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_DEPLOYMENT_TYPE", "datarobot-workload-preview")
        monkeypatch.delenv("MCP_WORKLOAD_IMAGE_URI", raising=False)
        import importlib

        import infra.mcp_server as mcp_infra

        return_value: dict[str, Any] = {
            "execution_environment": MagicMock(),
            "deployment": None,
            "mcp_server_mcp_endpoint": "ep",
            "mcp_server_base_endpoint": "base",
            "mcp_custom_model_runtime_parameters": [],
        }
        with patch(
            "infra.mcp_server_infra.workload.provision_workload_mcp_server",
            return_value=return_value,
        ) as mock_build:
            importlib.reload(mcp_infra)
            actual = mock_build.called
            expected = True
            assert actual == expected

    def test_mcp_deployment_type_exits_when_invalid(self, monkeypatch) -> None:
        monkeypatch.setenv("MCP_DEPLOYMENT_TYPE", "invalid-type")
        import importlib

        import infra.mcp_server as mcp_infra

        with (
            patch.object(sys, "exit", side_effect=SystemExit(1)) as mock_exit,
            pytest.raises(SystemExit),
        ):
            importlib.reload(mcp_infra)
        actual = mock_exit.call_args.args[0]
        expected = 1
        assert actual == expected
