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
from collections import namedtuple
from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, Mock, patch

from dev_tools.lineage.pulumi_managers import (
    MCPPromptMetadataPulumiManager,
    MCPResourceMetadataPulumiManager,
    MCPToolMetadataPulumiManager,
)
from infra.mcp_server_infra import deployment
from infra.mcp_server_infra.mcp_cli_configs import (
    DYNAMIC_FLAGS,
    TOOL_FLAGS,
)


@contextmanager
def env(**variables: str | None):
    originals = {name: os.environ.get(name) for name in variables}
    try:
        for name, value in variables.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, original in originals.items():
            if original is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = original


class MockOutput(MagicMock):
    def __init__(self, val=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply = MagicMock(side_effect=lambda fn, v=val: fn(v))

    @classmethod
    def secret(cls, val):
        return cls(val)


RuntimeParam = namedtuple(
    "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
)


@contextmanager
def stub_deployment(*, prediction_environment_id: str | None = None):
    mock_ee = MagicMock(id="ee-id", version_id="ee-ver")
    mock_deployment = MagicMock(id=MockOutput("dep-id"))
    mock_custom_model = MagicMock(version_id="model-ver")
    mock_use_case = MagicMock(id="use-case-id")
    mock_prediction_environment = MagicMock()
    mock_custom_model_cls = MagicMock(return_value=mock_custom_model)
    mock_load_metadata = Mock()
    with ExitStack() as stack:
        stack.enter_context(
            env(DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT=prediction_environment_id)
        )
        stack.enter_context(
            patch.object(
                deployment, "provision_mcp_execution_environment", return_value=mock_ee
            )
        )
        stack.enter_context(patch.object(deployment, "use_case", mock_use_case))
        stack.enter_context(patch.object(deployment.pulumi, "export", MagicMock()))
        stack.enter_context(patch.object(deployment.pulumi, "info", MagicMock()))
        stack.enter_context(patch.object(deployment.pulumi, "Output", MockOutput))
        stack.enter_context(
            patch.object(
                deployment.pulumi_datarobot,
                "CustomModel",
                mock_custom_model_cls,
            )
        )
        stack.enter_context(
            patch.object(deployment.pulumi_datarobot, "RegisteredModel", MagicMock())
        )
        stack.enter_context(
            patch.object(
                deployment.pulumi_datarobot,
                "PredictionEnvironment",
                mock_prediction_environment,
            )
        )
        stack.enter_context(
            patch.object(
                deployment.pulumi_datarobot, "Deployment", return_value=mock_deployment
            )
        )
        stack.enter_context(
            patch.object(deployment.pulumi_datarobot, "ApiTokenCredential", MagicMock())
        )
        stack.enter_context(
            patch.object(
                deployment.pulumi_datarobot, "ApiTokenCredentialArgs", MagicMock()
            )
        )
        stack.enter_context(
            patch.object(
                deployment.pulumi_datarobot,
                "CustomModelRuntimeParameterValueArgs",
                RuntimeParam,
            )
        )
        stack.enter_context(
            patch.object(deployment.pulumi_datarobot, "CustomModelTagArgs", MagicMock())
        )
        stack.enter_context(
            patch.object(
                MCPToolMetadataPulumiManager, "load_metadata", mock_load_metadata
            )
        )
        stack.enter_context(
            patch.object(
                MCPToolMetadataPulumiManager, "create_pulumi_resources", Mock()
            )
        )
        stack.enter_context(
            patch.object(
                MCPToolMetadataPulumiManager, "export_summary_to_pulumi_stack", Mock()
            )
        )
        stack.enter_context(
            patch.object(MCPPromptMetadataPulumiManager, "load_metadata", Mock())
        )
        stack.enter_context(
            patch.object(
                MCPPromptMetadataPulumiManager, "create_pulumi_resources", Mock()
            )
        )
        stack.enter_context(
            patch.object(
                MCPPromptMetadataPulumiManager, "export_summary_to_pulumi_stack", Mock()
            )
        )
        stack.enter_context(
            patch.object(MCPResourceMetadataPulumiManager, "load_metadata", Mock())
        )
        stack.enter_context(
            patch.object(
                MCPResourceMetadataPulumiManager, "create_pulumi_resources", Mock()
            )
        )
        stack.enter_context(
            patch.object(
                MCPResourceMetadataPulumiManager,
                "export_summary_to_pulumi_stack",
                Mock(),
            )
        )
        yield {
            "execution_environment": mock_ee,
            "custom_model": mock_custom_model,
            "deployment": mock_deployment,
            "prediction_environment": mock_prediction_environment,
            "custom_model_cls": mock_custom_model_cls,
            "load_metadata": mock_load_metadata,
        }


class TestEnabledToolsRuntimeParams:
    def test_enabled_tools_runtime_params_uses_tool_flags(self) -> None:
        actual = deployment._enabled_tools_runtime_params(set())
        expected = len(TOOL_FLAGS)
        assert len(actual) == expected


class TestDynamicRegistrationRuntimeParams:
    def test_dynamic_registration_runtime_params_uses_dynamic_flags(self) -> None:
        actual = deployment._dynamic_registration_runtime_params(set())
        expected = len(DYNAMIC_FLAGS)
        assert len(actual) == expected


class TestProvisionDeploymentMcpServer:
    def test_provision_creates_prediction_environment_when_env_not_set(self) -> None:
        with stub_deployment(prediction_environment_id=None) as mocks:
            deployment.provision_deployment_mcp_server(
                mcp_server_asset_name="srv",
                get_deployments_app_files=list,
            )
            actual = mocks["prediction_environment"].called
            expected = True
            assert actual == expected

    def test_provision_uses_existing_prediction_environment_when_env_set(self) -> None:
        with stub_deployment(prediction_environment_id="existing-pred-env-id") as mocks:
            deployment.provision_deployment_mcp_server(
                mcp_server_asset_name="srv",
                get_deployments_app_files=list,
            )
            actual = mocks["prediction_environment"].get.called
            expected = True
            assert actual == expected

    def test_provision_creates_custom_model_with_expected_name(self) -> None:
        with stub_deployment(prediction_environment_id=None) as mocks:
            deployment.provision_deployment_mcp_server(
                mcp_server_asset_name="srv",
                get_deployments_app_files=lambda: [("/tmp/app.py", "app.py")],
            )
            actual = mocks["custom_model_cls"].call_args.kwargs["name"]
            expected = "srv"
            assert actual == expected

    def test_provision_exports_lineage_metadata(self) -> None:
        with stub_deployment(prediction_environment_id=None) as mocks:
            deployment.provision_deployment_mcp_server(
                mcp_server_asset_name="srv",
                get_deployments_app_files=list,
            )
            actual = mocks["load_metadata"].called
            expected = True
            assert actual == expected
