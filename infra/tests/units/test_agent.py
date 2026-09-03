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
"""Tests for infra.agent (the entry router): runtime dispatch only.

Everything runtime-specific is unit-tested in test_agent_deployment.py.jinja
and test_agent_workload.py.jinja; this file only proves the
ENABLE_AGENT_ON_WORKLOAD_API branch picks the right one and never both.
"""

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _result_dict(tag: str, *, runtime: str = "generic") -> dict[str, Any]:
    result: dict[str, Any] = {
        "execution_environment": f"{tag}-execution-environment",
        "deployment": f"{tag}-deployment",
        "workload": f"{tag}-workload",
        "agent_serving_endpoint": f"{tag}-serving-endpoint",
        "agent_a2a_endpoint": f"{tag}-a2a-endpoint",
        "app_runtime_parameters": [f"{tag}-app-param"],
        "agent_runtime_parameters": [f"{tag}-agent-param"],
    }
    if runtime == "cm":
        result.update(
            {
                "custom_model": f"{tag}-custom-model",
                "agent_deployment_id": f"{tag}-deployment-id",
                "prediction_environment": f"{tag}-prediction-environment",
                "registered_model_args": f"{tag}-registered-model-args",
                "deployment_args": f"{tag}-deployment-args",
            }
        )
    else:
        result.update(
            {
                "custom_model": None,
                "agent_deployment_id": None,
                "prediction_environment": None,
                "registered_model_args": None,
                "deployment_args": None,
            }
        )
    return result


@pytest.fixture(autouse=True)
def router_mocks(monkeypatch, tmp_path):
    # Python 3.14+ no longer auto-creates an event loop on the main thread,
    # but Pulumi resource registration needs one when infra is first imported.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    monkeypatch.setattr("datarobot_pulumi_utils.pulumi.export", MagicMock())
    monkeypatch.setattr("pulumi.export", MagicMock())
    monkeypatch.setattr("pulumi.info", MagicMock())

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

    # Mocked *before* deployment.py is first imported below: pydantic caches
    # DeploymentArgs' compiled schema against whatever these classes are at
    # that moment, for the life of the process. If deployment.py's first-ever
    # import (across the whole test session) happened with the real classes,
    # test_agent_deployment.py's own mocks (applied post-import)
    # would no longer satisfy pydantic's `is_instance_of` check.
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

    import infra.agent_infra.base as base
    import infra.agent_infra.deployment as deployment
    import infra.agent_infra.workload as workload

    monkeypatch.setattr(
        base, "build_shared_agent_runtime_parameters", MagicMock(return_value=[])
    )
    deployment_mock = MagicMock(return_value=_result_dict("cm", runtime="cm"))
    workload_mock = MagicMock(return_value=_result_dict("wapi", runtime="wapi"))
    monkeypatch.setattr(deployment, "provision_deployment_agent", deployment_mock)
    monkeypatch.setattr(workload, "provision_workload_agent", workload_mock)

    yield deployment_mock, workload_mock
    loop.close()
    asyncio.set_event_loop(None)


def _reload_router():
    """Reload infra.agent so its module-level dispatch re-runs with this
    test's mocks. Guard against the first-ever import already running the
    dispatch once: reloading on top of that would double-count calls."""
    already_imported = "infra.agent" in sys.modules
    import infra.agent as agent_infra

    if already_imported:
        importlib.reload(agent_infra)
    return agent_infra


class TestRuntimeDispatch:
    def test_defaults_to_custom_models(self, monkeypatch, router_mocks):
        monkeypatch.delenv("ENABLE_AGENT_ON_WORKLOAD_API", raising=False)
        deployment_mock, workload_mock = router_mocks

        agent_infra = _reload_router()

        deployment_mock.assert_called_once()
        workload_mock.assert_not_called()
        assert agent_infra.agent_execution_environment == "cm-execution-environment"
        assert agent_infra.agent_agent_deployment == "cm-deployment"
        assert agent_infra.agent_workload == "cm-workload"

    def test_workload_api_enabled_skips_custom_models(self, monkeypatch, router_mocks):
        monkeypatch.setenv("ENABLE_AGENT_ON_WORKLOAD_API", "true")
        deployment_mock, workload_mock = router_mocks

        agent_infra = _reload_router()

        workload_mock.assert_called_once()
        deployment_mock.assert_not_called()
        assert agent_infra.agent_workload == "wapi-workload"
        assert agent_infra.agent_agent_deployment == "wapi-deployment"
        assert agent_infra.agent_execution_environment == "wapi-execution-environment"

    @pytest.mark.parametrize(
        "value", ["true", "TRUE", "1", "yes", "enabled", "Enabled"]
    )
    def test_truthy_values_select_workload_api(self, monkeypatch, router_mocks, value):
        monkeypatch.setenv("ENABLE_AGENT_ON_WORKLOAD_API", value)
        deployment_mock, workload_mock = router_mocks

        _reload_router()

        workload_mock.assert_called_once()
        deployment_mock.assert_not_called()

    @pytest.mark.parametrize("value", ["false", "0", "no", "", "garbage"])
    def test_non_truthy_values_select_custom_models(
        self, monkeypatch, router_mocks, value
    ):
        monkeypatch.setenv("ENABLE_AGENT_ON_WORKLOAD_API", value)
        deployment_mock, workload_mock = router_mocks

        _reload_router()

        deployment_mock.assert_called_once()
        workload_mock.assert_not_called()

    def test_shared_runtime_parameters_computed_once_and_passed_to_runtime(
        self, monkeypatch, router_mocks
    ):
        monkeypatch.delenv("ENABLE_AGENT_ON_WORKLOAD_API", raising=False)
        deployment_mock, _ = router_mocks
        import infra.agent_infra.base as base

        sentinel_params = ["shared-param-sentinel"]
        monkeypatch.setattr(
            base,
            "build_shared_agent_runtime_parameters",
            MagicMock(return_value=sentinel_params),
        )

        _reload_router()

        base.build_shared_agent_runtime_parameters.assert_called_once()
        deployment_mock.assert_called_once_with(sentinel_params)

    def test_re_exports_runtime_parameters(self, monkeypatch, router_mocks):
        monkeypatch.delenv("ENABLE_AGENT_ON_WORKLOAD_API", raising=False)

        agent_infra = _reload_router()

        assert agent_infra.agent_app_runtime_parameters == ["cm-app-param"]
        assert agent_infra.agent_agent_runtime_parameters == ["cm-agent-param"]
        assert agent_infra.agent_agent_serving_endpoint == "cm-serving-endpoint"
        assert agent_infra.agent_agent_a2a_endpoint == "cm-a2a-endpoint"

    def test_re_exports_backward_compatible_custom_models_symbols(
        self, monkeypatch, router_mocks
    ):
        monkeypatch.delenv("ENABLE_AGENT_ON_WORKLOAD_API", raising=False)
        import infra.agent_infra.base as base

        agent_infra = _reload_router()

        assert agent_infra.agent_application_name == base.agent_application_name
        assert agent_infra.agent_application_path == base.agent_application_path
        assert agent_infra.agent_custom_model == "cm-custom-model"
        assert agent_infra.agent_agent_deployment_id == "cm-deployment-id"
        assert agent_infra.agent_prediction_environment == "cm-prediction-environment"
        assert agent_infra.agent_registered_model_args == "cm-registered-model-args"
        assert agent_infra.agent_deployment_args == "cm-deployment-args"

    def test_re_exports_backward_compatible_workload_symbols_are_none(
        self, monkeypatch, router_mocks
    ):
        monkeypatch.setenv("ENABLE_AGENT_ON_WORKLOAD_API", "true")
        import infra.agent_infra.base as base

        agent_infra = _reload_router()

        assert agent_infra.agent_application_name == base.agent_application_name
        assert agent_infra.agent_application_path == base.agent_application_path
        assert agent_infra.agent_custom_model is None
        assert agent_infra.agent_agent_deployment_id is None
        assert agent_infra.agent_prediction_environment is None
        assert agent_infra.agent_registered_model_args is None
        assert agent_infra.agent_deployment_args is None
