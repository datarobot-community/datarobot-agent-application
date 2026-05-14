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
from collections import namedtuple

# Ensure the test directory is in sys.path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

AGENT_MEMORY_TTL_SECONDS = "AGENT_MEMORY_TTL_SECONDS"


# Patch all Pulumi resources and functions used in the module
@pytest.fixture(autouse=True)
def pulumi_mocks(monkeypatch, tmp_path):
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    # Mock infra.__init__ exported objects
    mock_use_case = MagicMock()
    mock_use_case.id = "mock-use-case-id"
    mock_project_dir = tmp_path
    monkeypatch.setattr("infra.use_case", mock_use_case)
    monkeypatch.setattr("infra.project_dir", mock_project_dir)

    # Mock out the LLM and just expose the runtime parameters as it is the only public
    # interface required for this module.
    mock_llm_module = MagicMock()
    mock_llm_module.custom_model_runtime_parameters = []
    monkeypatch.setitem(sys.modules, "infra.llm", mock_llm_module)
    # Mock out the MCP Server and just expose the runtime parameters as it is the only public
    # interface required for this module.
    mock_mcp_module = MagicMock()
    mock_mcp_module.mcp_custom_model_runtime_parameters = []
    monkeypatch.setitem(sys.modules, "infra.mcp_server", mock_mcp_module)
    # Mock pulumi_datarobot resources
    monkeypatch.setattr("pulumi_datarobot.ExecutionEnvironment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.CustomModel", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredentialArgs", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.Playground", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.LlmBlueprint", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.PredictionEnvironment", MagicMock())
    monkeypatch.setattr(
        "pulumi_datarobot.DeploymentAssociationIdSettingsArgs", MagicMock()
    )
    monkeypatch.setattr(
        "pulumi_datarobot.DeploymentPredictionsDataCollectionSettingsArgs", MagicMock()
    )
    monkeypatch.setattr(
        "pulumi_datarobot.DeploymentPredictionsSettingsArgs", MagicMock()
    )
    monkeypatch.setattr(
        "pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs", MagicMock()
    )

    # Mock CustomModelRuntimeParameterValueArgs to return simple namedtuple objects
    # Namedtuples are YAML-safe and have the attributes we need
    RuntimeParam = namedtuple(
        "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
    )

    monkeypatch.setattr(
        "pulumi_datarobot.CustomModelRuntimeParameterValueArgs", RuntimeParam
    )

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

    # Mock CustomModelDeployment
    monkeypatch.setattr(
        "datarobot_pulumi_utils.pulumi.custom_model_deployment.CustomModelDeployment",
        MagicMock(),
    )

    # Mock datarobot.ExecutionEnvironmentVersion.get to return a successful version by default
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

    # Mock Output to behave like a Pulumi Output with .apply(), support subscript notation, and from_input
    class MockOutput(MagicMock):
        def __new__(cls, val=None, *args, **kwargs):
            m = super().__new__(cls)
            m.apply = MagicMock(side_effect=lambda fn: fn(val))
            return m

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    # Set from_input() and format() as class methods that can be tracked
    MockOutput.from_input = MagicMock()
    MockOutput.format = MagicMock()
    monkeypatch.setattr("pulumi.Output", MockOutput)

    # Mock ApiTokenCredential to return a mock with .id as a pulumi.Output
    # This prevents MagicMock objects from being serialized to YAML
    def create_api_token_credential(*args, **kwargs):
        credential = MagicMock()
        # Create a mock that will be recognized as pulumi.Output by isinstance check
        output_mock = MagicMock(spec=MockOutput)
        output_mock.__class__ = MockOutput
        credential.id = output_mock
        return credential

    monkeypatch.setattr(
        "pulumi_datarobot.ApiTokenCredential", create_api_token_credential
    )

    yield
    patcher.stop()


def test_execution_environment_not_set_and_docker_context(monkeypatch):
    """Test execution environment creation when DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT is not set"""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset the mock to clear calls from the initial import
    agent_infra.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    agent_infra.pulumi.info.reset_mock()
    importlib.reload(agent_infra)

    # Check that pulumi.info was called with the correct message for docker_context.tar.gz
    agent_infra.pulumi.info.assert_any_call(
        "Using docker_context folder to compile the execution environment"
    )

    # Check that ExecutionEnvironment constructor was called correctly
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.ExecutionEnvironment.call_args

    assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"
    assert kwargs["programming_language"] == "python"
    assert kwargs["name"] == "[unittest] [agent] Execution Environment"
    assert kwargs["description"] == "Execution Environment for [unittest] [agent]"  # fmt: skip
    assert "docker_context_path" in kwargs
    assert "docker_image" not in kwargs
    assert kwargs["use_cases"] == ["customModel", "notebook"]

    # ExecutionEnvironment.get should not be called when env var is not set
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


def test_execution_environment_not_set_with_docker_image(monkeypatch):
    """Test execution environment creation when DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT is not set and docker_context.tar.gz exists"""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

    # Mock os.path.exists to return True for docker_context.tar.gz
    def mock_exists(path):
        if path.endswith("docker_context.tar.gz"):
            return True
        return False

    monkeypatch.setattr("os.path.exists", mock_exists)

    import importlib
    import infra.agent as agent_infra

    # Reset the mock to clear calls from the initial import
    agent_infra.pulumi_datarobot.ExecutionEnvironment.reset_mock()
    agent_infra.pulumi.info.reset_mock()
    importlib.reload(agent_infra)

    # Check that pulumi.info was called with the correct message for docker_context.tar.gz
    agent_infra.pulumi.info.assert_any_call(
        "Using prebuilt Dockerfile docker_context.tar.gz to run the execution environment"
    )

    # Check that ExecutionEnvironment constructor was called correctly
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.ExecutionEnvironment.call_args

    assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"
    assert kwargs["programming_language"] == "python"
    assert kwargs["name"] == "[unittest] [agent] Execution Environment"
    assert kwargs["description"] == "Execution Environment for [unittest] [agent]"  # fmt: skip
    assert "docker_image" in kwargs
    assert "docker_context_path" not in kwargs
    assert kwargs["use_cases"] == ["customModel", "notebook"]

    # ExecutionEnvironment.get should not be called when env var is not set
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


def test_execution_environment_default_set(monkeypatch):
    """Test execution environment when DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT is set to default value"""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT",
        "[DataRobot] Python 3.11 GenAI Agents",
    )

    import importlib
    import infra.agent as agent_infra

    importlib.reload(agent_infra)

    # Check that pulumi.info was called with the correct message
    agent_infra.pulumi.info.assert_any_call(
        "Using default GenAI Agentic Execution Environment."
    )
    agent_infra.pulumi.info.assert_any_call(
        "No valid execution environment version ID provided, using latest version."
    )

    # Check that ExecutionEnvironment.get was called with the correct parameters
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "python-311-genai-agents-id"
    assert kwargs["version_id"] is None
    assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"

    # ExecutionEnvironment constructor should not be called when using default env
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_execution_environment_pinned_set(monkeypatch):
    """Test execution environment when DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT is set to default value"""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT",
        "[DataRobot] Python 3.11 GenAI Agents",
    )
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
        "69e2134aa5df12076d70afe7",
    )

    import importlib
    import infra.agent as agent_infra

    importlib.reload(agent_infra)

    # Check that pulumi.info was called with the correct message
    agent_infra.pulumi.info.assert_any_call(
        "Using default GenAI Agentic Execution Environment."
    )
    agent_infra.pulumi.info.assert_any_call(
        "Using existing execution environment: python-311-genai-agents-id Version ID: 69e2134aa5df12076d70afe7"
    )

    # Check that ExecutionEnvironment.get was called with the correct parameters
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "python-311-genai-agents-id"
    assert kwargs["version_id"] == "69e2134aa5df12076d70afe7"
    assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"

    # ExecutionEnvironment constructor should not be called when using default env
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_execution_environment_custom_set(monkeypatch):
    """Test execution environment when DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT is set to a custom value"""
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", "Custom Execution Environment"
    )

    import importlib
    import infra.agent as agent_infra

    importlib.reload(agent_infra)

    # Check that pulumi.info was called with the correct message
    agent_infra.pulumi.info.assert_any_call(
        "No valid execution environment version ID provided, using latest version."
    )
    agent_infra.pulumi.info.assert_any_call(
        "Using existing execution environment: Custom Execution Environment Version ID: None"
    )

    # Check that ExecutionEnvironment.get was called with the correct parameters
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.ExecutionEnvironment.get.call_args

    assert kwargs["id"] == "Custom Execution Environment"
    assert kwargs["version_id"] is None
    assert kwargs["resource_name"] == "[unittest] [agent] Execution Environment"

    # ExecutionEnvironment constructor should not be called when using custom env
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_not_called()


def test_resolve_execution_environment_version_not_found_returns_none(monkeypatch):
    """When pinned EE version is not found in DataRobot, warn and return None (use latest)."""
    import infra.agent as agent_infra
    from datarobot.errors import ClientError

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
        "69e2134aa5df12076d70afe7",
    )
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(side_effect=ClientError("Version not found", 404)),
    )

    version_id = agent_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    agent_infra.pulumi.warn.assert_called_once()
    call_msg = agent_infra.pulumi.warn.call_args[0][0]
    assert "69e2134aa5df12076d70afe7" in call_msg
    assert "using latest" in call_msg


def test_resolve_execution_environment_version_found(monkeypatch):
    """When pinned version exists and build_status is SUCCESS, return its id."""
    import infra.agent as agent_infra
    from datarobot.enums import EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
        "abcdef0123456789abcdef01",
    )
    mock_version = MagicMock()
    mock_version.id = "abcdef0123456789abcdef01"
    mock_version.build_status = EXECUTION_ENVIRONMENT_VERSION_BUILD_STATUS.SUCCESS
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=mock_version),
    )

    version_id = agent_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id == "abcdef0123456789abcdef01"
    agent_infra.pulumi.warn.assert_not_called()


def test_resolve_execution_environment_version_not_success_returns_none(monkeypatch):
    """When get() succeeds but build_status is not SUCCESS, return None with a warning."""
    import infra.agent as agent_infra

    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
        "abcdef0123456789abcdef01",
    )
    mock_version = MagicMock()
    mock_version.id = "abcdef0123456789abcdef01"
    mock_version.build_status = "processing"
    monkeypatch.setattr(
        "datarobot.ExecutionEnvironmentVersion.get",
        MagicMock(return_value=mock_version),
    )

    version_id = agent_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    agent_infra.pulumi.warn.assert_called_once()
    call_msg = agent_infra.pulumi.warn.call_args[0][0]
    assert "abcdef0123456789abcdef01" in call_msg
    assert "using latest" in call_msg


def test_resolve_execution_environment_version_unset_returns_none(monkeypatch):
    """When env var is unset or invalid, return None without calling DR API."""
    import infra.agent as agent_infra

    monkeypatch.delenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID", raising=False
    )
    mock_get = MagicMock()
    monkeypatch.setattr("datarobot.ExecutionEnvironmentVersion.get", mock_get)

    version_id = agent_infra.resolve_execution_environment_version(
        "ee-base-id",
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    assert version_id is None
    mock_get.assert_not_called()
    agent_infra.pulumi.warn.assert_not_called()


def test_reset_environment_between_tests():
    """Test to ensure that environment variables don't leak between tests"""
    # This test should run with no environment variables set from previous tests
    assert os.environ.get("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT") is None

    import importlib
    import infra.agent as agent_infra

    importlib.reload(agent_infra)

    # Default behavior should be to create a new execution environment
    agent_infra.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
    agent_infra.pulumi_datarobot.ExecutionEnvironment.get.assert_not_called()


def test_custom_model_created(monkeypatch):
    """Test that pulumi_datarobot.CustomModel is created with correct arguments."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.delenv(AGENT_MEMORY_TTL_SECONDS, raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset the mock to clear calls from the initial import
    agent_infra.pulumi_datarobot.CustomModel.reset_mock()

    environment_variables = {
        "SESSION_SECRET_KEY": "secret_value",
        "MEM0_API_KEY": "some_mem0_api_key",
    }
    with patch.dict(os.environ, environment_variables):
        importlib.reload(agent_infra)

    agent_infra.pulumi_datarobot.CustomModel.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.CustomModel.call_args
    assert kwargs["resource_name"] == "[unittest] [agent] Custom Model"
    assert kwargs["name"] == "[unittest] [agent] Custom Model"
    assert kwargs["base_environment_id"] == agent_infra.agent_execution_environment.id  # fmt: skip
    assert (
        kwargs["base_environment_version_id"]
        == agent_infra.agent_execution_environment.version_id
    )
    assert kwargs["target_type"] == "AgenticWorkflow"
    assert kwargs["target_name"] == "response"
    assert kwargs["language"] == "python"
    assert kwargs["use_case_ids"] == [agent_infra.use_case.id]
    assert isinstance(kwargs["files"], list)

    runtime_parameter_values = kwargs["runtime_parameter_values"]

    # Should have 6 params: 1 SESSION_SECRET_KEY + 5 DRUM params
    assert len(runtime_parameter_values) == 6

    # Find the SESSION_SECRET_KEY parameter
    session_secret_param = next(
        (p for p in runtime_parameter_values if p.key == "SESSION_SECRET_KEY"), None
    )
    assert session_secret_param is not None
    assert session_secret_param.type == "credential"
    assert session_secret_param.value is not None

    memory_ttl_param = next(
        (p for p in runtime_parameter_values if p.key == AGENT_MEMORY_TTL_SECONDS),
        None,
    )
    assert memory_ttl_param is None


def test_custom_model_created_pinned_version_id(monkeypatch):
    """Test that pulumi_datarobot.CustomModel is created with correct arguments."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.setenv(
        "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID", "69e2134aa5df12076d70afe7"
    )
    monkeypatch.setattr(
        "pulumi_datarobot.ExecutionEnvironment",
        MagicMock(
            return_value=MagicMock(
                id="default-id", version_id="69e2134aa5df12076d70afe7"
            )
        ),
    )

    import importlib
    import infra.agent as agent_infra

    # Reset the mock to clear calls from the initial import
    agent_infra.pulumi_datarobot.CustomModel.reset_mock()

    environment_variables = {
        "SESSION_SECRET_KEY": "secret_value",
    }
    with patch.dict(os.environ, environment_variables):
        importlib.reload(agent_infra)

    agent_infra.pulumi_datarobot.CustomModel.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.CustomModel.call_args
    assert kwargs["base_environment_id"] == "default-id"
    assert kwargs["base_environment_version_id"] == "69e2134aa5df12076d70afe7"


def test_custom_model_resource_bundle_and_replicas(monkeypatch):
    """Test that CustomModel is created with correct resource_bundle_id and replicas."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENABLE_AGENT_HA_MODE", raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset the mock to clear calls from the initial import
    agent_infra.pulumi_datarobot.CustomModel.reset_mock()
    importlib.reload(agent_infra)

    agent_infra.pulumi_datarobot.CustomModel.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.CustomModel.call_args

    # Verify resource_bundle_id is set to cpu.3xlarge (non-HA default)
    assert kwargs["resource_bundle_id"] == "cpu.3xlarge"

    # Verify replicas is set to 1
    assert kwargs["replicas"] == 1


def test_custom_model_resource_bundle_and_replicas_ha_mode(monkeypatch):
    """HA mode uses larger resource bundle and multiple replicas."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "true")

    import importlib
    import infra.agent as agent_infra

    agent_infra.pulumi_datarobot.CustomModel.reset_mock()
    importlib.reload(agent_infra)

    agent_infra.pulumi_datarobot.CustomModel.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.CustomModel.call_args
    assert kwargs["resource_bundle_id"] == "cpu.5xlarge"
    assert kwargs["replicas"] == 2


def test_agentic_playground_and_blueprint_created(monkeypatch):
    """Test that pulumi_datarobot.Playground and pulumi_datarobot.LlmBlueprint are created
    and the Playground URL is added to outputs."""
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
    monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://example.datarobot.com/api/v2")

    import importlib
    import infra.agent as agent_infra

    # Reset the mocks to clear calls from the initial import
    agent_infra.pulumi_datarobot.Playground.reset_mock()
    agent_infra.pulumi_datarobot.LlmBlueprint.reset_mock()
    agent_infra.pulumi.export.reset_mock()
    importlib.reload(agent_infra)

    # Check that Agentic Playground was created
    agent_infra.pulumi_datarobot.Playground.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.Playground.call_args
    assert kwargs["resource_name"] == "[unittest] [agent] Agentic Playground"
    assert kwargs["name"] == "[unittest] [agent] Agentic Playground"
    assert kwargs["use_case_id"] == agent_infra.use_case.id
    assert kwargs["playground_type"] == "agentic"

    # Check that LlmBlueprint was created and points to the created custom model
    agent_infra.pulumi_datarobot.LlmBlueprint.assert_called_once()
    args, kwargs = agent_infra.pulumi_datarobot.LlmBlueprint.call_args
    assert kwargs["resource_name"] == "[unittest] [agent] LLM Blueprint"
    assert kwargs["name"] == "[unittest] [agent] LLM Blueprint"
    assert kwargs["llm_id"] == "chat-interface-custom-model"
    assert kwargs["prompt_type"] == "ONE_TIME_PROMPT"
    assert kwargs[
        "llm_settings"
    ] == agent_infra.pulumi_datarobot.LlmBlueprintLlmSettingsArgs(
        custom_model_id=agent_infra.agent_custom_model.id
    )

    # Check that we export agent Playground URL from pulumi
    export_names = [call.args[0] for call in agent_infra.pulumi.export.call_args_list]
    assert "Agent Playground URL " + agent_infra.agent_asset_name in export_names  # fmt: skip

    # Check the format of the URL
    agent_infra.pulumi.Output.format.assert_any_call(
        "{0}/usecases/{1}/agentic-playgrounds/{2}/comparison/chats",
        "https://example.datarobot.com",
        "mock-use-case-id",
        agent_infra.agent_playground.id,
    )


def test_agent_deployment_created_when_env(monkeypatch):
    """Test that agent deployment resources are created when AGENT_DEPLOY is not '0'."""
    monkeypatch.setenv("AGENT_DEPLOY", "1")
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset mocks to clear calls from the initial import
    agent_infra.pulumi_datarobot.PredictionEnvironment.reset_mock()
    agent_infra.pulumi_datarobot.DeploymentAssociationIdSettingsArgs.reset_mock()
    agent_infra.pulumi_datarobot.DeploymentPredictionsDataCollectionSettingsArgs.reset_mock()
    agent_infra.CustomModelDeployment.reset_mock()
    importlib.reload(agent_infra)

    # Check that PredictionEnvironment was created
    agent_infra.pulumi_datarobot.PredictionEnvironment.assert_called_once()
    # Check that CustomModelDeployment was created
    agent_infra.CustomModelDeployment.assert_called_once()
    agent_infra.pulumi.export.assert_any_call(
        "Agent Deployment Chat Endpoint " + agent_infra.agent_asset_name,
        agent_infra.CustomModelDeployment.return_value.id.apply.return_value,
    )


def test_agent_deployment_uses_existing_prediction_environment(monkeypatch):
    """Test that an existing prediction environment is used when DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT is set."""
    monkeypatch.setenv("AGENT_DEPLOY", "1")
    monkeypatch.setenv("DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT", "existing-pe-id")
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset mocks to clear calls from the initial import
    agent_infra.pulumi_datarobot.PredictionEnvironment.reset_mock()
    agent_infra.CustomModelDeployment.reset_mock()
    importlib.reload(agent_infra)

    # Check that PredictionEnvironment.get() was called with the existing ID
    agent_infra.pulumi_datarobot.PredictionEnvironment.get.assert_called_once()
    _, call_kwargs = agent_infra.pulumi_datarobot.PredictionEnvironment.get.call_args
    assert call_kwargs.get("id") == "existing-pe-id"
    # Check that PredictionEnvironment constructor was not called
    agent_infra.pulumi_datarobot.PredictionEnvironment.assert_not_called()
    # Check that CustomModelDeployment was still created
    agent_infra.CustomModelDeployment.assert_called_once()


def test_agent_deployment_not_created_when_env_zero(monkeypatch):
    """Test that agent deployment resources are not created when AGENT_DEPLOY is '0'."""
    monkeypatch.setenv("AGENT_DEPLOY", "0")
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

    import importlib
    import infra.agent as agent_infra

    # Reset mocks to clear calls from the initial import
    agent_infra.pulumi_datarobot.PredictionEnvironment.reset_mock()
    agent_infra.CustomModelDeployment.reset_mock()
    importlib.reload(agent_infra)

    # Check that PredictionEnvironment and CustomModelDeployment were not called
    agent_infra.pulumi_datarobot.PredictionEnvironment.assert_not_called()
    agent_infra.CustomModelDeployment.assert_not_called()


class TestUpdateDeploymentPredictionsSettings:
    """Tests for the _update_deployment_predictions_settings workaround."""

    def test_gets_current_settings_then_patches(self, monkeypatch):
        """Test that the function GETs current settings, merges overrides, and PATCHes."""
        import infra.agent as agent_infra

        # Create a mock DR client
        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {
            "predictionsSettings": {
                "realTime": True,
                "minComputes": 1,
                "maxComputes": 1,
                "autoscalingPolicy": {
                    "triggers": [{"type": "cpu", "targetValue": 40}],
                    "cooldownPeriod": 5,
                },
            }
        }
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        result = agent_infra._update_deployment_predictions_settings(
            deployment_id="test-deployment-id",
            min_computes=0,
            max_computes=4,
        )

        # Verify GET was called
        mock_client.get.assert_called_once_with(
            "deployments/test-deployment-id/settings/"
        )

        # Verify PATCH was called with merged settings (preserving autoscalingPolicy)
        mock_client.patch.assert_called_once_with(
            "deployments/test-deployment-id/settings/",
            json={
                "predictionsSettings": {
                    "realTime": True,
                    "minComputes": 0,
                    "maxComputes": 4,
                    "autoscalingPolicy": {
                        "triggers": [{"type": "cpu", "targetValue": 40}],
                        "cooldownPeriod": 5,
                    },
                }
            },
        )

        # Verify it returns the deployment ID
        assert result == "test-deployment-id"

    def test_handles_empty_predictions_settings(self, monkeypatch):
        """Test that the function handles missing predictionsSettings in GET response."""
        import infra.agent as agent_infra

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        agent_infra._update_deployment_predictions_settings(
            deployment_id="test-deployment-id",
            min_computes=0,
            max_computes=2,
        )

        # Verify PATCH was called with just our overrides
        mock_client.patch.assert_called_once_with(
            "deployments/test-deployment-id/settings/",
            json={
                "predictionsSettings": {
                    "minComputes": 0,
                    "maxComputes": 2,
                }
            },
        )

    def test_uses_default_constants(self, monkeypatch):
        """Test that the apply call uses the DEFAULT constants."""
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

        # Mock dr.Client so the apply callback doesn't make real API calls
        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        # Make CustomModelDeployment.id.apply actually call the function
        mock_deployment = MagicMock()
        mock_deployment.id.apply = MagicMock(
            side_effect=lambda fn: fn("mock-deployment-id")
        )
        monkeypatch.setattr(
            "datarobot_pulumi_utils.pulumi.custom_model_deployment.CustomModelDeployment",
            MagicMock(return_value=mock_deployment),
        )

        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        # Verify the PATCH was called with the correct constant values
        mock_client.patch.assert_called_once()
        patch_kwargs = mock_client.patch.call_args
        patched_settings = patch_kwargs[1]["json"]["predictionsSettings"]
        assert (
            patched_settings["minComputes"]
            == agent_infra.DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES
        )
        assert (
            patched_settings["maxComputes"]
            == agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES
        )

    def test_rejects_invalid_min_computes(self):
        """Test that min_computes must be 0 or equal to max_computes."""
        import infra.agent as agent_infra

        with pytest.raises(
            ValueError,
            match=r"(?s)Invalid deployment configuration.*min_computes must be either 0 or equal to max_computes",
        ):
            agent_infra._update_deployment_predictions_settings(
                deployment_id="test-deployment-id",
                min_computes=1,
                max_computes=4,
            )

    def test_accepts_min_computes_zero(self, monkeypatch):
        """Test that min_computes=0 is accepted."""
        import infra.agent as agent_infra

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        result = agent_infra._update_deployment_predictions_settings(
            deployment_id="test-deployment-id",
            min_computes=0,
            max_computes=4,
        )
        assert result == "test-deployment-id"

    def test_accepts_min_computes_equal_to_max(self, monkeypatch):
        """Test that min_computes equal to max_computes is accepted."""
        import infra.agent as agent_infra

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        result = agent_infra._update_deployment_predictions_settings(
            deployment_id="test-deployment-id",
            min_computes=4,
            max_computes=4,
        )
        assert result == "test-deployment-id"


class TestEnableAgentHAMode:
    def test_ha_mode_disabled_by_default(self, monkeypatch):
        """Test that HA mode is disabled by default."""
        monkeypatch.delenv("ENABLE_AGENT_HA_MODE", raising=False)
        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        assert agent_infra.ENABLE_AGENT_HA_MODE is False
        assert agent_infra.DEFAULT_CUSTOM_MODEL_WORKERS == "2"
        assert agent_infra.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.3xlarge"
        assert agent_infra.DEFAULT_AGENT_REPLICAS == 1
        assert agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 2

    def test_ha_mode_disabled_explicit_false(self, monkeypatch):
        """Test that HA mode is disabled when explicitly set to 'false'."""
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "false")
        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        assert agent_infra.ENABLE_AGENT_HA_MODE is False
        assert agent_infra.DEFAULT_CUSTOM_MODEL_WORKERS == "2"
        assert agent_infra.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.3xlarge"
        assert agent_infra.DEFAULT_AGENT_REPLICAS == 1
        assert agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 2

    def test_ha_mode_enabled(self, monkeypatch):
        """Test that HA mode is enabled when set to 'true'."""
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "true")
        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        assert agent_infra.ENABLE_AGENT_HA_MODE is True
        assert agent_infra.DEFAULT_CUSTOM_MODEL_WORKERS == "5"
        assert agent_infra.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.5xlarge"
        assert agent_infra.DEFAULT_AGENT_REPLICAS == 2
        assert agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 4

    def test_ha_mode_case_insensitive(self, monkeypatch):
        """Test that HA mode accepts 'true' in any case, but not other truthy values."""
        test_cases = [
            ("True", True),
            ("TRUE", True),
            ("1", False),
            ("yes", False),
            ("on", False),
        ]

        for value, expected in test_cases:
            monkeypatch.setenv("ENABLE_AGENT_HA_MODE", value)
            import importlib
            import infra.agent as agent_infra

            importlib.reload(agent_infra)

            assert agent_infra.ENABLE_AGENT_HA_MODE is expected
            if expected:
                assert agent_infra.DEFAULT_CUSTOM_MODEL_WORKERS == "5"
                assert agent_infra.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.5xlarge"
                assert agent_infra.DEFAULT_AGENT_REPLICAS == 2
                assert agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 4
            else:
                assert agent_infra.DEFAULT_CUSTOM_MODEL_WORKERS == "2"
                assert agent_infra.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.3xlarge"
                assert agent_infra.DEFAULT_AGENT_REPLICAS == 1
                assert agent_infra.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 2


class TestGetCustomModelFiles:
    def test_get_custom_model_files_basic(self, tmp_path):
        import infra.agent as agent_infra

        # Create a simple file structure
        (tmp_path / "file1.py").write_text("print('hi')")
        (tmp_path / "file2.txt").write_text("hello")
        files = agent_infra.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "file1.py" in file_names
        assert "file2.txt" in file_names

        # Autogenerated metadata file
        assert "model-metadata.yaml" in file_names
        assert len(files) == 3

    def test_get_custom_model_files_excludes(self, tmp_path):
        import infra.agent as agent_infra

        # Create files that should be excluded
        (tmp_path / "file1.py").write_text("print('hi')")
        (tmp_path / ".DS_Store").write_text("")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "foo.pyc").write_text("")
        files = agent_infra.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "file1.py" in file_names
        assert ".DS_Store" not in file_names
        assert "__pycache__/foo.pyc" not in file_names

        # Autogenerated metadata file
        assert "model-metadata.yaml" in file_names
        assert len(files) == 2

    def test_get_custom_model_files_excludes_docker_context(self, tmp_path):
        import infra.agent as agent_infra

        # Create files including a docker_context directory that should be excluded
        (tmp_path / "file1.py").write_text("print('hi')")
        docker_context_dir = tmp_path / "docker_context"
        docker_context_dir.mkdir()
        (docker_context_dir / "docker_file.py").write_text("print('docker')")

        files = agent_infra.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]

        assert "file1.py" in file_names
        assert "docker_context/docker_file.py" not in file_names

    def test_get_custom_model_files_symlinks(self, tmp_path):
        import infra.agent as agent_infra

        # Create a real file and a symlink to it
        real_file = tmp_path / "real.py"
        real_file.write_text("print('hi')")
        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.mkdir()
        symlink = symlink_dir / "link.py"
        symlink.symlink_to(real_file)
        files = agent_infra.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "real.py" in file_names


class TestSynchronizePyprojectDependencies:
    def test_synchronize_pyproject_dependencies_basic(self, tmp_path, monkeypatch):
        import infra.agent as agent_infra

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create pyproject.toml in the application path
        pyproject_content = """[project]
name = "test-project"
dependencies = ["requests>=2.0"]
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        (tmp_path / "uv.lock").write_text("test content")

        # Create docker_context directory
        (tmp_path / "docker_context").mkdir()

        # Call the function
        agent_infra.synchronize_pyproject_dependencies()

        # Check that pyproject.toml was copied to docker_context
        assert (tmp_path / "docker_context" / "pyproject.toml").exists()
        assert (tmp_path / "docker_context" / "uv.lock").exists()

        # Verify the content is the same
        assert (
            tmp_path / "docker_context" / "pyproject.toml"
        ).read_text() == pyproject_content
        assert (tmp_path / "docker_context" / "uv.lock").read_text() == "test content"

    def test_synchronize_pyproject_dependencies_no_pyproject(
        self, tmp_path, monkeypatch
    ):
        import infra.agent as agent_infra

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create docker_context directory but no pyproject.toml
        (tmp_path / "docker_context").mkdir()

        # Call the function - should return early without error
        agent_infra.synchronize_pyproject_dependencies()

        # Check that no pyproject.toml files were created
        assert not (tmp_path / "docker_context" / "pyproject.toml").exists()

    def test_synchronize_pyproject_dependencies_missing_docker_context_dir(
        self, tmp_path, monkeypatch
    ):
        import infra.agent as agent_infra

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create pyproject.toml but not docker_context
        pyproject_content = """[project]
name = "test-project"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)

        # Call the function
        agent_infra.synchronize_pyproject_dependencies()

        # Check that no docker_context directory was created
        assert not (tmp_path / "docker_context").exists()

    def test_synchronize_pyproject_dependencies_overwrites_existing(
        self, tmp_path, monkeypatch
    ):
        import infra.agent as agent_infra

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create pyproject.toml in the application path
        new_content = """[project]
name = "updated-project"
dependencies = ["requests>=3.0"]
"""
        (tmp_path / "pyproject.toml").write_text(new_content)

        # Create docker_context directory with existing pyproject.toml file
        (tmp_path / "docker_context").mkdir()

        old_content = """[project]
name = "old-project"
"""
        (tmp_path / "docker_context" / "pyproject.toml").write_text(old_content)

        # Call the function
        agent_infra.synchronize_pyproject_dependencies()

        # Check that the old file was overwritten with new content
        assert (
            tmp_path / "docker_context" / "pyproject.toml"
        ).read_text() == new_content


class TestMaybeImportFromModule:
    @pytest.fixture
    def skip_if_no_mcp(self):
        """Skip tests if mcp module is not available."""
        mcp_module = "mcp_server"
        if not mcp_module:
            pytest.skip("Skipping tests of existing MCP when module is not provided.")

    @pytest.mark.usefixtures("skip_if_no_mcp")
    def test_maybe_import_from_module_success(self):
        """Test that maybe_import_from_module successfully imports an existing module."""
        import infra.agent as agent_infra

        # The fixture sets up the mocked MCP module with mcp_custom_model_runtime_parameters
        result = agent_infra.maybe_import_from_module(
            "mcp_server", "mcp_custom_model_runtime_parameters"
        )
        assert result is not None

    def test_maybe_import_from_module_missing_module(self, monkeypatch):
        """Test that maybe_import_from_module returns None when module is not available."""
        import infra.agent as agent_infra

        # Mock importlib.import_module to raise ImportError
        def mock_import_module(name, package=None):
            raise ImportError(f"No module named '{name}'")

        monkeypatch.setattr("importlib.import_module", mock_import_module)

        # Attempt to import from the non-existent module
        result = agent_infra.maybe_import_from_module(
            "mcp_server", "mcp_custom_model_runtime_parameters"
        )
        assert result is None

    def test_maybe_import_from_module_empty_module_name(self):
        """Test that maybe_import_from_module returns None with empty module name."""
        import infra.agent as agent_infra

        result = agent_infra.maybe_import_from_module("", "some_attribute")
        assert result is None


class TestGetMcpCustomModelRuntimeParameters:
    def test_get_mcp_custom_model_runtime_parameters_from_module(self):
        """Test that MCP runtime parameters are loaded from the module when available."""
        import infra.agent as agent_infra

        result = agent_infra.get_mcp_custom_model_runtime_parameters()
        # The fixture sets up a mock module with empty list
        assert isinstance(result, list)

    def test_get_mcp_custom_model_runtime_parameters_fallback_to_env(self, monkeypatch):
        """Test that MCP runtime parameters fall back to environment variables when module is unavailable."""
        import infra.agent as agent_infra

        # Set up environment variables
        monkeypatch.setenv("MCP_DEPLOYMENT_ID", "test-deployment-123")
        monkeypatch.setenv("EXTERNAL_MCP_URL", "https://example.com/mcp")
        monkeypatch.setenv(
            "EXTERNAL_MCP_HEADERS", '{"Authorization": "Bearer token123"}'
        )
        monkeypatch.setenv("EXTERNAL_MCP_TRANSPORT", "sse")

        # Mock importlib.import_module to raise ImportError
        def mock_import_module(name, package=None):
            raise ImportError(f"No module named '{name}'")

        monkeypatch.setattr("importlib.import_module", mock_import_module)

        # Get runtime parameters - should fall back to environment variables
        result = agent_infra.get_mcp_custom_model_runtime_parameters()

        assert isinstance(result, list)
        assert len(result) == 4

        # Check MCP_DEPLOYMENT_ID parameter
        mcp_deployment_param = next(
            (p for p in result if p.key == "MCP_DEPLOYMENT_ID"), None
        )
        assert mcp_deployment_param is not None
        assert mcp_deployment_param.type == "string"
        assert mcp_deployment_param.value == "test-deployment-123"

        # Check EXTERNAL_MCP_URL parameter
        external_mcp_param = next(
            (p for p in result if p.key == "EXTERNAL_MCP_URL"), None
        )
        assert external_mcp_param is not None
        assert external_mcp_param.type == "string"
        assert external_mcp_param.value == "https://example.com/mcp"

        # Check EXTERNAL_MCP_HEADERS parameter
        external_mcp_headers_param = next(
            (p for p in result if p.key == "EXTERNAL_MCP_HEADERS"), None
        )
        assert external_mcp_headers_param is not None
        assert external_mcp_headers_param.type == "string"
        assert external_mcp_headers_param.value == (
            '{"Authorization": "Bearer token123"}'
        )

        # Check EXTERNAL_MCP_TRANSPORT parameter
        external_mcp_transport_param = next(
            (p for p in result if p.key == "EXTERNAL_MCP_TRANSPORT"), None
        )
        assert external_mcp_transport_param is not None
        assert external_mcp_transport_param.type == "string"
        assert external_mcp_transport_param.value == "sse"


class TestGenerateMetadataYaml:
    def test_mixed_parameters(self, tmp_path, monkeypatch):
        """Test _generate_metadata_yaml with various parameter types to verify defaultValue behavior."""
        import infra.agent as agent_infra
        import yaml  # type: ignore[import-untyped]

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create mixed runtime parameters with different types
        # Use simple objects instead of MagicMock to avoid YAML serialization issues
        RuntimeParam = namedtuple("RuntimeParam", ["key", "type", "value"])
        mock_params = [
            # String parameter with value - should NOT have defaultValue
            RuntimeParam(
                key="LLM_DEPLOYMENT_ID", type="string", value="some-string-value"
            ),
            # Credential parameter - should NOT have defaultValue
            RuntimeParam(key="SESSION_SECRET_KEY", type="credential", value=None),
            # DRUM numeric parameter - should HAVE defaultValue (in allowlist)
            RuntimeParam(key="CUSTOM_MODEL_WORKERS", type="numeric", value="5"),
            # DRUM string parameter - should HAVE defaultValue (in allowlist)
            RuntimeParam(key="DRUM_SERVER_TYPE", type="string", value="gunicorn"),
            # String parameter with special characters - should NOT have defaultValue (not in allowlist)
            RuntimeParam(
                key="EXTERNAL_MCP_HEADERS", type="string", value='{"auth": "token"}'
            ),
        ]

        # Call the function with tmp_path as the custom model folder
        agent_infra._generate_metadata_yaml("agent", str(tmp_path), mock_params)

        # Read and parse the generated YAML
        metadata_file = tmp_path / "model-metadata.yaml"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)

        # Verify metadata structure
        assert metadata["name"] == "agent"
        assert metadata["type"] == "inference"
        assert metadata["targetType"] == "agenticworkflow"

        # Verify parameters maintain order and correct types
        params = metadata["runtimeParameterDefinitions"]

        assert len(params) == 5

        # String parameter - should NOT have defaultValue (not in allowlist)
        assert params[0]["fieldName"] == "LLM_DEPLOYMENT_ID"
        assert params[0]["type"] == "string"
        assert "defaultValue" not in params[0], (
            "String parameters not in allowlist should not have defaultValue"
        )

        # Credential parameter - should NOT have defaultValue
        assert params[1]["fieldName"] == "SESSION_SECRET_KEY"
        assert params[1]["type"] == "credential"
        assert "defaultValue" not in params[1]
        assert "credentialType" not in params[1]

        # DRUM numeric parameter - should HAVE defaultValue (in allowlist)
        assert params[2]["fieldName"] == "CUSTOM_MODEL_WORKERS"
        assert params[2]["type"] == "numeric"
        assert "defaultValue" in params[2], (
            "DRUM parameters in allowlist should have defaultValue"
        )
        assert params[2]["defaultValue"] == "5"

        # DRUM string parameter - should HAVE defaultValue (in allowlist)
        assert params[3]["fieldName"] == "DRUM_SERVER_TYPE"
        assert params[3]["type"] == "string"
        assert "defaultValue" in params[3], (
            "DRUM parameters in allowlist should have defaultValue"
        )
        assert params[3]["defaultValue"] == "gunicorn"

        # String parameter with sensitive data - should NOT have defaultValue (not in allowlist)
        assert params[4]["fieldName"] == "EXTERNAL_MCP_HEADERS"
        assert params[4]["type"] == "string"
        assert "defaultValue" not in params[4], (
            "String parameters with sensitive data should not have defaultValue"
        )

    def test_with_empty_parameters(self, tmp_path, monkeypatch):
        """Test _generate_metadata_yaml generates correct YAML with empty parameter list."""
        import infra.agent as agent_infra
        import yaml  # type: ignore[import-untyped]

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Call with empty parameters
        agent_infra._generate_metadata_yaml("agent", str(tmp_path), [])

        # Read and parse the generated YAML
        metadata_file = tmp_path / "model-metadata.yaml"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)

        # Verify structure
        assert metadata["name"] == "agent"
        assert metadata["type"] == "inference"
        assert metadata["targetType"] == "agenticworkflow"
        assert metadata["runtimeParameterDefinitions"] == []

    def test_format_and_overwrite(self, tmp_path, monkeypatch):
        """Test _generate_metadata_yaml file formatting and overwrite behavior."""
        import infra.agent as agent_infra
        import yaml  # type: ignore[import-untyped]

        # Mock the application path to point to our tmp_path
        monkeypatch.setattr(agent_infra, "agent_application_path", tmp_path)

        # Create an existing file with different content
        metadata_file = tmp_path / "model-metadata.yaml"
        metadata_file.write_text("old: content\n")

        # Use simple object instead of MagicMock to avoid YAML serialization issues
        RuntimeParam = namedtuple("RuntimeParam", ["key", "type", "value"])
        mock_params = [RuntimeParam(key="NEW_PARAM", type="string", value=None)]
        agent_infra._generate_metadata_yaml("agent", str(tmp_path), mock_params)

        # Check raw file format
        content = metadata_file.read_text()
        assert content.startswith("---\n")
        assert "name: agent" in content
        assert "type: inference" in content
        assert "targetType: agenticworkflow" in content
        assert "runtimeParameterDefinitions:" in content
        assert "fieldName: NEW_PARAM" in content

        # Verify the old file was overwritten
        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)

        assert "old" not in metadata
        assert metadata["name"] == "agent"
        assert metadata["runtimeParameterDefinitions"][0]["fieldName"] == "NEW_PARAM"


class TestAgentMemoryRuntimeParameter:
    def test_ttl_runtime_parameter_excluded_when_memory_disabled(self, monkeypatch):
        """Test that the agent memory TTL runtime parameter is excluded by default."""
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
        monkeypatch.setenv(AGENT_MEMORY_TTL_SECONDS, "86400")

        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        memory_ttl_param = next(
            (
                param
                for param in agent_infra.agent_runtime_parameter_values
                if param.key == AGENT_MEMORY_TTL_SECONDS
            ),
            None,
        )

        assert memory_ttl_param is None


class TestDrumRuntimeParameters:
    def test_drum_runtime_parameters_included(self, monkeypatch):
        """Test that DRUM concurrency runtime parameters are included in agent_runtime_parameter_values."""
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

        import importlib
        import infra.agent as agent_infra

        importlib.reload(agent_infra)

        # Get all DRUM-related parameters
        drum_params = {
            param.key: param
            for param in agent_infra.agent_runtime_parameter_values
            if param.key
            in [
                "CUSTOM_MODEL_WORKERS",
                "DRUM_SERVER_TYPE",
                "DRUM_GUNICORN_WORKER_CLASS",
                "DRUM_WORKER_CONNECTIONS",
                "DRUM_CLIENT_REQUEST_TIMEOUT",
            ]
        }

        # Verify all 5 DRUM parameters are present
        assert len(drum_params) == 5

        # Check CUSTOM_MODEL_WORKERS
        assert drum_params["CUSTOM_MODEL_WORKERS"].type == "numeric"
        assert drum_params["CUSTOM_MODEL_WORKERS"].value == "2"

        # Check DRUM_SERVER_TYPE
        assert drum_params["DRUM_SERVER_TYPE"].type == "string"
        assert drum_params["DRUM_SERVER_TYPE"].value == "gunicorn"

        # Check DRUM_GUNICORN_WORKER_CLASS
        assert drum_params["DRUM_GUNICORN_WORKER_CLASS"].type == "string"
        assert drum_params["DRUM_GUNICORN_WORKER_CLASS"].value == "sync"

        # Check DRUM_WORKER_CONNECTIONS
        assert drum_params["DRUM_WORKER_CONNECTIONS"].type == "numeric"
        assert drum_params["DRUM_WORKER_CONNECTIONS"].value == "1"

        # Check DRUM_CLIENT_REQUEST_TIMEOUT
        assert drum_params["DRUM_CLIENT_REQUEST_TIMEOUT"].type == "numeric"
        assert drum_params["DRUM_CLIENT_REQUEST_TIMEOUT"].value == "300"

    def test_drum_runtime_parameters_passed_to_custom_model(self, monkeypatch):
        """Test that DRUM runtime parameters are passed to CustomModel."""
        monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)

        import importlib
        import infra.agent as agent_infra

        agent_infra.pulumi_datarobot.CustomModel.reset_mock()
        importlib.reload(agent_infra)

        agent_infra.pulumi_datarobot.CustomModel.assert_called_once()
        _, kwargs = agent_infra.pulumi_datarobot.CustomModel.call_args

        runtime_params = kwargs["runtime_parameter_values"]
        drum_keys = [
            "CUSTOM_MODEL_WORKERS",
            "DRUM_SERVER_TYPE",
            "DRUM_GUNICORN_WORKER_CLASS",
            "DRUM_WORKER_CONNECTIONS",
            "DRUM_CLIENT_REQUEST_TIMEOUT",
        ]

        found_keys = [param.key for param in runtime_params if param.key in drum_keys]
        assert set(found_keys) == set(drum_keys)
