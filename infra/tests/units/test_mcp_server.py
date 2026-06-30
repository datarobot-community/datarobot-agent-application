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
import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from unittest.mock import Mock
from collections import namedtuple

from dev_tools.lineage.pulumi_managers import MCPToolMetadataPulumiManager
from dev_tools.lineage.pulumi_managers import MCPPromptMetadataPulumiManager
from dev_tools.lineage.pulumi_managers import MCPResourceMetadataPulumiManager

# Ensure the test directory is in sys.path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))


# Patch all Pulumi resources and functions used in the module
@pytest.fixture(autouse=True)
def pulumi_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    # Neutralize the module-level export() calls in infra.__init__ before the
    # first infra import below triggers them outside a pulumi Stack context.
    monkeypatch.setattr("datarobot_pulumi_utils.pulumi.export", MagicMock())
    # Mock infra.__init__ exported objects
    mock_use_case = MagicMock()
    mock_use_case.id = "mock-use-case-id"
    mock_project_dir = tmp_path
    monkeypatch.setattr("infra.use_case", mock_use_case)
    monkeypatch.setattr("infra.project_dir", mock_project_dir)

    # Create the mcp app directory structure expected by module-level code.
    # deployments_application_path = project_dir.parent / "mcp_server"
    mcp_app_dir = tmp_path.parent / "mcp_server"
    mcp_app_dir.mkdir(exist_ok=True)

    # Mock user params module
    mock_user_params_module = MagicMock()
    mock_user_params_module.MCP_USER_RUNTIME_PARAMETERS = []
    monkeypatch.setitem(
        sys.modules, "infra.mcp_server_user_params", mock_user_params_module
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

    # Mock Output to behave like a Pulumi Output with .apply()
    class MockOutput(MagicMock):
        def __new__(cls, val=None, *args, **kwargs):
            m = super().__new__(cls)
            m.apply = MagicMock(side_effect=lambda fn: fn(val))
            return m

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    MockOutput.from_input = MagicMock()
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


def test_execution_environment_not_set_uses_docker(monkeypatch):
    """Test execution environment creation when DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT is not set."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    mcp_infra.pulumi.info.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using docker folder to compile the execution environment"
    )

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.call_args

    assert kwargs["programming_language"] == "python"
    assert "docker_context_path" in kwargs

    # ExecutionEnvironment.get should not be called when env var is not set
    mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


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
    args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

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
    args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

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
    args, kwargs = mcp_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "Custom Execution Environment"
    assert kwargs["version_id"] is None

    mcp_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_resolve_execution_environment_version_not_found_returns_none(monkeypatch):
    """When pinned EE version is not found in DataRobot, warn and return None (use latest)."""
    import infra.mcp_server as mcp_infra
    from datarobot.errors import ClientError

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
    import infra.mcp_server as mcp_infra
    from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

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


def test_prediction_environment_created_when_env_var_not_set(monkeypatch):
    """Test that a new PredictionEnvironment is created when DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT is not set."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.PredictionEnvironment.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi_datarobot.PredictionEnvironment.assert_called_once()
    mcp_infra.pulumi_datarobot.PredictionEnvironment.get.assert_not_called()


def test_prediction_environment_injected_when_env_var_set(monkeypatch):
    """Test that an existing PredictionEnvironment is used when DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT is set."""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT", "existing-pred-env-id"
    )

    import importlib
    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.PredictionEnvironment.reset_mock()
    mcp_infra.pulumi.info.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi.info.assert_any_call(
        "Using existing prediction environment 'existing-pred-env-id'"
    )

    mcp_infra.pulumi_datarobot.PredictionEnvironment.get.assert_called_once()
    args, kwargs = mcp_infra.pulumi_datarobot.PredictionEnvironment.get.call_args
    assert kwargs["id"] == "existing-pred-env-id"

    mcp_infra.pulumi_datarobot.PredictionEnvironment.assert_not_called()


def test_custom_model_created(monkeypatch):
    """Test that pulumi_datarobot.CustomModel is created with correct arguments."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.mcp_server as mcp_infra

    mcp_infra.pulumi_datarobot.CustomModel.reset_mock()
    importlib.reload(mcp_infra)

    mcp_infra.pulumi_datarobot.CustomModel.assert_called_once()
    args, kwargs = mcp_infra.pulumi_datarobot.CustomModel.call_args
    assert kwargs["resource_name"] == "[unittest] [mcp_server] Custom Model"
    assert kwargs["name"] == "[unittest] [mcp_server]"
    assert kwargs["description"] == "MCP server"
    assert kwargs["language"] == "python"
    assert kwargs["base_environment_id"] == mcp_infra.execution_environment.id
    assert (
        kwargs["base_environment_version_id"]
        == mcp_infra.execution_environment.version_id
    )
    assert kwargs["use_case_ids"] == [mcp_infra.use_case.id]
    assert isinstance(kwargs["files"], list)


def test_mcp_item_lineage_metadata(monkeypatch):
    import importlib
    import infra.mcp_server as mcp_infra

    load_tool_metadata = mcp_infra.MCPToolMetadataPulumiManager.load_metadata
    create_pulumi_tool_resources = (
        mcp_infra.MCPToolMetadataPulumiManager.create_pulumi_resources
    )
    export_tool_summary_to_pulumi_stack = (
        mcp_infra.MCPToolMetadataPulumiManager.export_summary_to_pulumi_stack
    )
    load_prompt_metadata = mcp_infra.MCPPromptMetadataPulumiManager.load_metadata
    create_pulumi_prompt_resources = (
        mcp_infra.MCPPromptMetadataPulumiManager.create_pulumi_resources
    )
    export_prompt_summary_to_pulumi_stack = (
        mcp_infra.MCPPromptMetadataPulumiManager.export_summary_to_pulumi_stack
    )
    load_resource_metadata = mcp_infra.MCPResourceMetadataPulumiManager.load_metadata
    create_pulumi_resource_resources = (
        mcp_infra.MCPResourceMetadataPulumiManager.create_pulumi_resources
    )
    export_resource_summary_to_pulumi_stack = (
        mcp_infra.MCPResourceMetadataPulumiManager.export_summary_to_pulumi_stack
    )
    load_tool_metadata.reset_mock()
    create_pulumi_tool_resources.reset_mock()
    export_tool_summary_to_pulumi_stack.reset_mock()
    load_prompt_metadata.reset_mock()
    create_pulumi_prompt_resources.reset_mock()
    export_prompt_summary_to_pulumi_stack.reset_mock()
    load_resource_metadata.reset_mock()
    create_pulumi_resource_resources.reset_mock()
    export_resource_summary_to_pulumi_stack.reset_mock()
    importlib.reload(mcp_infra)

    mock_custom_model = mcp_infra.pulumi_datarobot.CustomModel.return_value
    expected_actual_mcp_server_asset_name = "[unittest] [mcp_server]"
    # check saving MCP tool metadata through pulumi
    mcp_infra.MCPToolMetadataPulumiManager.load_metadata.assert_called_once_with()
    args, _ = mcp_infra.MCPToolMetadataPulumiManager.create_pulumi_resources.call_args
    (
        actual_mcp_metadata_entities,
        actual_mcp_server_asset_name,
        actual_custom_model_version_id,
    ) = args
    assert actual_mcp_metadata_entities == load_tool_metadata.return_value
    assert actual_mcp_server_asset_name == expected_actual_mcp_server_asset_name
    assert actual_custom_model_version_id == mock_custom_model.version_id
    args, _ = (
        mcp_infra.MCPToolMetadataPulumiManager.export_summary_to_pulumi_stack.call_args
    )
    (
        actual_mcp_server_asset_name,
        actual_mcp_metadata_pulumi_resources,
    ) = args
    assert (
        actual_mcp_metadata_pulumi_resources
        == create_pulumi_tool_resources.return_value
    )
    # check saving MCP prompt metadata through pulumi
    mcp_infra.MCPPromptMetadataPulumiManager.load_metadata.assert_called_once_with()
    args, _ = mcp_infra.MCPPromptMetadataPulumiManager.create_pulumi_resources.call_args
    (
        actual_mcp_metadata_entities,
        actual_mcp_server_asset_name,
        actual_custom_model_version_id,
    ) = args
    assert actual_mcp_metadata_entities == load_prompt_metadata.return_value
    assert actual_mcp_server_asset_name == expected_actual_mcp_server_asset_name
    assert actual_custom_model_version_id == mock_custom_model.version_id
    args, _ = (
        mcp_infra.MCPPromptMetadataPulumiManager.export_summary_to_pulumi_stack.call_args
    )
    (
        actual_mcp_server_asset_name,
        actual_mcp_metadata_pulumi_resources,
    ) = args
    assert (
        actual_mcp_metadata_pulumi_resources
        == create_pulumi_prompt_resources.return_value
    )
    # check saving MCP resource metadata through pulumi
    mcp_infra.MCPResourceMetadataPulumiManager.load_metadata.assert_called_once_with()
    args, _ = (
        mcp_infra.MCPResourceMetadataPulumiManager.create_pulumi_resources.call_args
    )
    (
        actual_mcp_metadata_entities,
        actual_mcp_server_asset_name,
        actual_custom_model_version_id,
    ) = args
    assert actual_mcp_metadata_entities == load_resource_metadata.return_value
    assert actual_mcp_server_asset_name == expected_actual_mcp_server_asset_name
    assert actual_custom_model_version_id == mock_custom_model.version_id
    args, _ = (
        mcp_infra.MCPResourceMetadataPulumiManager.export_summary_to_pulumi_stack.call_args
    )
    (
        actual_mcp_server_asset_name,
        actual_mcp_metadata_pulumi_resources,
    ) = args
    assert (
        actual_mcp_metadata_pulumi_resources
        == create_pulumi_resource_resources.return_value
    )
