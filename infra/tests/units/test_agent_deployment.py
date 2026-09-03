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
"""Tests for infra.agent_infra.deployment: the Custom Models runtime (default)."""

import asyncio
import importlib
import sys
from collections import namedtuple
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

RuntimeParam = namedtuple(
    "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
)


@pytest.fixture(autouse=True)
def deployment_mocks(monkeypatch, tmp_path):
    # Python 3.14+ no longer auto-creates an event loop on the main thread,
    # but Pulumi resource registration needs one when infra is first imported.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    monkeypatch.delenv("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", raising=False)
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
    monkeypatch.setattr("pulumi_datarobot.CustomModel", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.Playground", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.LlmBlueprint", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.PredictionEnvironment", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredentialArgs", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.MemorySpace", MagicMock())
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

    monkeypatch.setattr(
        "datarobot_pulumi_utils.pulumi.custom_model_deployment.CustomModelDeployment",
        MagicMock(),
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


def _reload_deployment():
    """Reload base then deployment, in that order (deployment's HA-derived module
    constants are computed at *its own* import time from base.ENABLE_AGENT_HA_MODE,
    itself fixed at *base's* import time)."""
    import infra.agent_infra.base as base
    import infra.agent_infra.deployment as deployment

    importlib.reload(base)
    importlib.reload(deployment)
    return deployment


class TestProvisionDeploymentAgent:
    def test_custom_model_created(self, monkeypatch):
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        shared_params = [
            RuntimeParam(key="SESSION_SECRET_KEY", type="credential", value="cred-id")
        ]
        result = deployment.provision_deployment_agent(shared_params)

        deployment.pulumi_datarobot.CustomModel.assert_called_once()
        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert kwargs["resource_name"] == "[unittest] [agent] Custom Model"
        assert kwargs["target_type"] == "AgenticWorkflow"
        assert kwargs["target_name"] == "response"
        assert kwargs["language"] == "python"
        assert kwargs["use_case_ids"] == [deployment.use_case.id]
        assert isinstance(kwargs["files"], list)

        runtime_parameter_values = kwargs["runtime_parameter_values"]
        assert any(p.key == "SESSION_SECRET_KEY" for p in runtime_parameter_values)
        workers_param = next(
            p for p in runtime_parameter_values if p.key == "CUSTOM_MODEL_WORKERS"
        )
        assert workers_param.type == "numeric"
        assert workers_param.value == "2"

        assert result["custom_model"] is not None
        assert result["playground"] is not None
        assert result["workload"] is None

    def test_custom_model_workers_precedes_gunicorn_timeout(self, monkeypatch):
        """CUSTOM_MODEL_WORKERS keeps the position it held before the infra split.

        base.py leaves it out (no Workload-container equivalent), so deployment.py
        has to put it back directly before AGENT_GUNICORN_WORKER_TIMEOUT rather than
        append it after the credential/memory params. Appending would reorder the
        runtimeParameterDefinitions block in the generated model-metadata.yaml and
        cost every upgrading project a spurious custom model version.
        """
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        shared_params = [
            RuntimeParam(key="LLM_DEPLOYMENT_ID", type="string", value="llm-id"),
            RuntimeParam(
                key="AGENT_GUNICORN_WORKER_TIMEOUT", type="string", value="600"
            ),
            RuntimeParam(key="SESSION_SECRET_KEY", type="credential", value="cred-id"),
        ]
        deployment.provision_deployment_agent(shared_params)

        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert [p.key for p in kwargs["runtime_parameter_values"]] == [
            "LLM_DEPLOYMENT_ID",
            "CUSTOM_MODEL_WORKERS",
            "AGENT_GUNICORN_WORKER_TIMEOUT",
            "SESSION_SECRET_KEY",
        ]

    def test_custom_model_workers_appended_when_timeout_absent(self, monkeypatch):
        """Falls back to appending when the shared list carries no timeout param."""
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        shared_params = [
            RuntimeParam(key="LLM_DEPLOYMENT_ID", type="string", value="llm-id")
        ]
        deployment.provision_deployment_agent(shared_params)

        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert [p.key for p in kwargs["runtime_parameter_values"]] == [
            "LLM_DEPLOYMENT_ID",
            "CUSTOM_MODEL_WORKERS",
        ]

    def test_execution_environment_id_passthrough(self, monkeypatch):
        deployment = _reload_deployment()
        mock_ee = MagicMock(id="default-id", version_id="69e2134aa5df12076d70afe7")
        monkeypatch.setattr(
            deployment.pulumi_datarobot,
            "ExecutionEnvironment",
            MagicMock(return_value=mock_ee),
        )
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        deployment.provision_deployment_agent([])

        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert kwargs["base_environment_id"] == "default-id"
        assert kwargs["base_environment_version_id"] == "69e2134aa5df12076d70afe7"

    def test_resource_bundle_and_replicas_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_AGENT_HA_MODE", raising=False)
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        deployment.provision_deployment_agent([])

        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert kwargs["resource_bundle_id"] == "cpu.xlarge"
        assert kwargs["replicas"] == 1

    def test_ha_derived_constants_explicit_false(self, monkeypatch):
        """'false' is disabled, same as unset -- the HA-derived module constants
        computed at deployment's import time must keep their non-HA values."""
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "false")
        deployment = _reload_deployment()

        assert deployment.base.ENABLE_AGENT_HA_MODE is False
        assert deployment.DEFAULT_CUSTOM_MODEL_WORKERS == "2"
        assert deployment.DEFAULT_AGENT_RESOURCE_BUNDLE_ID == "cpu.xlarge"
        assert deployment.DEFAULT_AGENT_REPLICAS == 1
        assert deployment.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES == 2

    def test_resource_bundle_and_replicas_ha_mode(self, monkeypatch):
        monkeypatch.setenv("ENABLE_AGENT_HA_MODE", "true")
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.CustomModel.reset_mock()

        deployment.provision_deployment_agent([])

        _, kwargs = deployment.pulumi_datarobot.CustomModel.call_args
        assert kwargs["resource_bundle_id"] == "cpu.3xlarge"
        assert kwargs["replicas"] == 2

        workers_param = next(
            p
            for p in kwargs["runtime_parameter_values"]
            if p.key == "CUSTOM_MODEL_WORKERS"
        )
        assert workers_param.value == "5"

    def test_playground_and_blueprint_created(self, monkeypatch):
        monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://example.datarobot.com/api/v2")
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.Playground.reset_mock()
        deployment.pulumi_datarobot.LlmBlueprint.reset_mock()
        deployment.pulumi.export.reset_mock()
        deployment.pulumi.Output.format.reset_mock()

        deployment.provision_deployment_agent([])

        deployment.pulumi_datarobot.Playground.assert_called_once()
        _, kwargs = deployment.pulumi_datarobot.Playground.call_args
        assert kwargs["resource_name"] == "[unittest] [agent] Agentic Playground"
        assert kwargs["use_case_id"] == deployment.use_case.id
        assert kwargs["playground_type"] == "agentic"

        deployment.pulumi_datarobot.LlmBlueprint.assert_called_once()
        _, kwargs = deployment.pulumi_datarobot.LlmBlueprint.call_args
        assert kwargs["llm_id"] == "chat-interface-custom-model"
        assert kwargs["prompt_type"] == "ONE_TIME_PROMPT"

        export_names = [
            call.args[0] for call in deployment.pulumi.export.call_args_list
        ]
        assert "Agent Playground URL [unittest] [agent]" in export_names

    def test_agent_deployment_created_when_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.PredictionEnvironment.reset_mock()
        deployment.CustomModelDeployment.reset_mock()

        result = deployment.provision_deployment_agent([])

        deployment.pulumi_datarobot.PredictionEnvironment.assert_called_once()
        deployment.CustomModelDeployment.assert_called_once()
        assert result["deployment"] is not None

    def test_agent_deployment_uses_existing_prediction_environment(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        monkeypatch.setenv("DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT", "existing-pe-id")
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.PredictionEnvironment.reset_mock()
        deployment.CustomModelDeployment.reset_mock()

        deployment.provision_deployment_agent([])

        deployment.pulumi_datarobot.PredictionEnvironment.get.assert_called_once()
        _, call_kwargs = deployment.pulumi_datarobot.PredictionEnvironment.get.call_args
        assert call_kwargs.get("id") == "existing-pe-id"
        deployment.pulumi_datarobot.PredictionEnvironment.assert_not_called()
        deployment.CustomModelDeployment.assert_called_once()

    def test_agent_deployment_not_created_when_env_zero(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "0")
        deployment = _reload_deployment()
        deployment.pulumi_datarobot.PredictionEnvironment.reset_mock()
        deployment.CustomModelDeployment.reset_mock()

        result = deployment.provision_deployment_agent([])

        deployment.pulumi_datarobot.PredictionEnvironment.assert_not_called()
        deployment.CustomModelDeployment.assert_not_called()
        assert result["deployment"] is None
        assert result["agent_serving_endpoint"] == "None"

    def test_workload_and_execution_environment_reported(self, monkeypatch):
        """Custom Models path always reports workload=None; execution_environment
        is the resolved EE (never None, unlike the Workload API image-URI path)."""
        deployment = _reload_deployment()

        result = deployment.provision_deployment_agent([])

        assert result["workload"] is None
        assert result["execution_environment"] is not None


class TestA2AEndpointRuntimeParameter:
    """Guard against silent A2A breakage: inject the deployment A2A endpoint runtime
    parameter when DRAgent and an A2A server block are both enabled."""

    A2A_ENDPOINT_PARAM_KEY = "AGENT_A2A_ENDPOINT"

    def test_present_when_a2a_enabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2")
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "IS_A2A_SERVER_ENABLED", True)

        result = deployment.provision_deployment_agent([])

        param_keys = [p.key for p in result["agent_runtime_parameters"]]
        assert self.A2A_ENDPOINT_PARAM_KEY in param_keys
        assert result["agent_a2a_endpoint"] is not None

    def test_absent_when_a2a_disabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2")
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "IS_A2A_SERVER_ENABLED", False)

        result = deployment.provision_deployment_agent([])

        param_keys = [p.key for p in result["agent_runtime_parameters"]]
        assert self.A2A_ENDPOINT_PARAM_KEY not in param_keys
        assert result["agent_a2a_endpoint"] is None


class TestUpdateDeploymentPredictionsSettings:
    def test_gets_current_settings_then_patches(self, monkeypatch):
        deployment = _reload_deployment()

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

        result = deployment._update_deployment_predictions_settings(
            deployment_id="test-deployment-id", min_computes=0, max_computes=4
        )

        mock_client.get.assert_called_once_with(
            "deployments/test-deployment-id/settings/"
        )
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
        assert result == "test-deployment-id"

    def test_handles_empty_predictions_settings(self, monkeypatch):
        deployment = _reload_deployment()

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        deployment._update_deployment_predictions_settings(
            deployment_id="test-deployment-id", min_computes=0, max_computes=2
        )

        mock_client.patch.assert_called_once_with(
            "deployments/test-deployment-id/settings/",
            json={"predictionsSettings": {"minComputes": 0, "maxComputes": 2}},
        )

    def test_rejects_invalid_min_computes(self):
        deployment = _reload_deployment()

        with pytest.raises(
            ValueError,
            match=r"(?s)Invalid deployment configuration.*min_computes must be either 0 or equal to max_computes",
        ):
            deployment._update_deployment_predictions_settings(
                deployment_id="test-deployment-id", min_computes=1, max_computes=4
            )

    def test_accepts_min_computes_zero(self, monkeypatch):
        deployment = _reload_deployment()

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        result = deployment._update_deployment_predictions_settings(
            deployment_id="test-deployment-id", min_computes=0, max_computes=4
        )
        assert result == "test-deployment-id"

    def test_accepts_min_computes_equal_to_max(self, monkeypatch):
        deployment = _reload_deployment()

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        result = deployment._update_deployment_predictions_settings(
            deployment_id="test-deployment-id", min_computes=4, max_computes=4
        )
        assert result == "test-deployment-id"

    def test_uses_default_constants_end_to_end(self, monkeypatch):
        monkeypatch.setenv("AGENT_DEPLOY", "1")
        deployment = _reload_deployment()

        mock_client = MagicMock()
        mock_client.get.return_value.json.return_value = {"predictionsSettings": {}}
        monkeypatch.setattr("datarobot.Client", MagicMock(return_value=mock_client))

        mock_deployment = MagicMock()
        mock_deployment.id.apply = MagicMock(
            side_effect=lambda fn: fn("mock-deployment-id")
        )
        monkeypatch.setattr(
            deployment, "CustomModelDeployment", MagicMock(return_value=mock_deployment)
        )

        deployment.provision_deployment_agent([])

        mock_client.patch.assert_called_once()
        patched_settings = mock_client.patch.call_args[1]["json"]["predictionsSettings"]
        assert (
            patched_settings["minComputes"]
            == deployment.DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES
        )
        assert (
            patched_settings["maxComputes"]
            == deployment.DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES
        )


class TestGetCustomModelFiles:
    def test_basic(self, tmp_path):
        deployment = _reload_deployment()

        (tmp_path / "file1.py").write_text("print('hi')")
        (tmp_path / "file2.txt").write_text("hello")
        files = deployment.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "file1.py" in file_names
        assert "file2.txt" in file_names
        assert "model-metadata.yaml" in file_names
        assert len(files) == 3

    def test_excludes(self, tmp_path):
        deployment = _reload_deployment()

        (tmp_path / "file1.py").write_text("print('hi')")
        (tmp_path / ".DS_Store").write_text("")
        (tmp_path / ".env").write_text("SECRET=token")
        (tmp_path / ".env.local").write_text("SECRET=token")
        (tmp_path / ".environment").write_text("not a secret file")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "foo.pyc").write_text("")
        files = deployment.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "file1.py" in file_names
        assert ".DS_Store" not in file_names
        assert ".env" not in file_names
        assert ".env.local" not in file_names
        assert ".environment" in file_names
        assert "__pycache__/foo.pyc" not in file_names
        assert "model-metadata.yaml" in file_names
        assert len(files) == 3

    def test_excludes_docker_context(self, tmp_path):
        deployment = _reload_deployment()

        (tmp_path / "file1.py").write_text("print('hi')")
        docker_context_dir = tmp_path / "docker_context"
        docker_context_dir.mkdir()
        (docker_context_dir / "docker_file.py").write_text("print('docker')")

        files = deployment.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "file1.py" in file_names
        assert "docker_context/docker_file.py" not in file_names

    def test_symlinks(self, tmp_path):
        deployment = _reload_deployment()

        real_file = tmp_path / "real.py"
        real_file.write_text("print('hi')")
        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.mkdir()
        symlink = symlink_dir / "link.py"
        symlink.symlink_to(real_file)
        files = deployment.get_custom_model_files(str(tmp_path), [])
        file_names = [f[1] for f in files]
        assert "real.py" in file_names


class TestSynchronizePyprojectDependencies:
    def test_basic(self, tmp_path, monkeypatch):
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "agent_application_path", tmp_path)

        pyproject_content = (
            '[project]\nname = "test-project"\ndependencies = ["requests>=2.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(pyproject_content)
        (tmp_path / "uv.lock").write_text("test content")
        (tmp_path / "docker_context").mkdir()

        deployment.synchronize_pyproject_dependencies()

        assert (tmp_path / "docker_context" / "pyproject.toml").exists()
        assert (tmp_path / "docker_context" / "uv.lock").exists()
        assert (
            tmp_path / "docker_context" / "pyproject.toml"
        ).read_text() == pyproject_content
        assert (tmp_path / "docker_context" / "uv.lock").read_text() == "test content"

    def test_no_pyproject(self, tmp_path, monkeypatch):
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "agent_application_path", tmp_path)
        (tmp_path / "docker_context").mkdir()

        deployment.synchronize_pyproject_dependencies()

        assert not (tmp_path / "docker_context" / "pyproject.toml").exists()

    def test_missing_docker_context_dir(self, tmp_path, monkeypatch):
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "agent_application_path", tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-project"\n')

        deployment.synchronize_pyproject_dependencies()

        assert not (tmp_path / "docker_context").exists()

    def test_overwrites_existing(self, tmp_path, monkeypatch):
        deployment = _reload_deployment()
        monkeypatch.setattr(deployment.base, "agent_application_path", tmp_path)

        new_content = (
            '[project]\nname = "updated-project"\ndependencies = ["requests>=3.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(new_content)
        (tmp_path / "docker_context").mkdir()
        (tmp_path / "docker_context" / "pyproject.toml").write_text(
            '[project]\nname = "old-project"\n'
        )

        deployment.synchronize_pyproject_dependencies()

        assert (
            tmp_path / "docker_context" / "pyproject.toml"
        ).read_text() == new_content


class TestGenerateMetadataYaml:
    def test_mixed_parameters(self, tmp_path):
        import yaml  # type: ignore[import-untyped]

        deployment = _reload_deployment()

        mock_params = [
            RuntimeParam(
                key="LLM_DEPLOYMENT_ID", type="string", value="some-string-value"
            ),
            RuntimeParam(key="SESSION_SECRET_KEY", type="credential", value=None),
            RuntimeParam(key="CUSTOM_MODEL_WORKERS", type="numeric", value="5"),
            RuntimeParam(
                key="EXTERNAL_MCP_HEADERS", type="string", value='{"auth": "token"}'
            ),
        ]

        deployment._generate_metadata_yaml("agent", str(tmp_path), mock_params)

        metadata_file = tmp_path / "model-metadata.yaml"
        assert metadata_file.exists()
        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)

        assert metadata["name"] == "agent"
        assert metadata["type"] == "inference"
        assert metadata["targetType"] == "agenticworkflow"

        params = metadata["runtimeParameterDefinitions"]
        assert len(params) == 4
        assert params[0]["fieldName"] == "LLM_DEPLOYMENT_ID"
        assert "defaultValue" not in params[0]
        assert params[1]["fieldName"] == "SESSION_SECRET_KEY"
        assert "defaultValue" not in params[1]
        assert params[2]["fieldName"] == "CUSTOM_MODEL_WORKERS"
        assert params[2]["defaultValue"] == "5"
        assert params[3]["fieldName"] == "EXTERNAL_MCP_HEADERS"
        assert "defaultValue" not in params[3]

    def test_with_empty_parameters(self, tmp_path):
        import yaml  # type: ignore[import-untyped]

        deployment = _reload_deployment()
        deployment._generate_metadata_yaml("agent", str(tmp_path), [])

        metadata_file = tmp_path / "model-metadata.yaml"
        with open(metadata_file) as f:
            metadata = yaml.safe_load(f)
        assert metadata["runtimeParameterDefinitions"] == []

    def test_format_and_overwrite(self, tmp_path):
        deployment = _reload_deployment()

        metadata_file = tmp_path / "model-metadata.yaml"
        metadata_file.write_text("old: content\n")

        mock_params = [RuntimeParam(key="NEW_PARAM", type="string", value=None)]
        deployment._generate_metadata_yaml("agent", str(tmp_path), mock_params)

        content = metadata_file.read_text()
        assert content.startswith("---\n")
        assert "name: agent" in content
        assert "fieldName: NEW_PARAM" in content
        assert "old" not in content
