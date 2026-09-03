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
"""Tests for infra.agent_infra.workload: the Workload API runtime."""

import asyncio
import sys
from collections import namedtuple
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pulumi
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

RuntimeParam = namedtuple(
    "RuntimeParam", ["key", "type", "value"], defaults=[None, None, None]
)


class FakeOutput:
    """Minimal stand-in for pulumi.Output that resolves .apply() synchronously."""

    def __init__(self, val):
        self._val = val

    def apply(self, fn):
        return FakeOutput(fn(self._val))

    def __eq__(self, other):
        if isinstance(other, FakeOutput):
            return self._val == other._val
        return self._val == other


def _fake_resource(**attrs: Any) -> MagicMock:
    """A MagicMock that passes real pulumi.ResourceOptions(depends_on=[...])
    validation (which requires actual pulumi.Resource instances), while still
    allowing arbitrary attribute access/assignment like a plain MagicMock."""
    mock = MagicMock()
    mock.__class__ = pulumi.Resource  # type: ignore[assignment]
    for key, value in attrs.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture(autouse=True)
def workload_env_mocks(monkeypatch, tmp_path):
    # Python 3.14+ no longer auto-creates an event loop on the main thread,
    # but Pulumi resource registration needs one when infra is first imported.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    monkeypatch.setenv("PULUMI_STACK_CONTEXT", "unittest")
    monkeypatch.setenv("DATAROBOT_API_TOKEN", "test-token")
    monkeypatch.setenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2")
    monkeypatch.delenv("WORKLOAD_AGENT_IMAGE_URI", raising=False)
    monkeypatch.delenv("WORKLOAD_ENTRYPOINT", raising=False)
    # A developer's own OTEL/execution-environment settings must not leak into
    # these assertions.
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
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
    monkeypatch.setattr("pulumi_datarobot.ApiTokenCredentialArgs", MagicMock())
    monkeypatch.setattr("pulumi_datarobot.MemorySpace", MagicMock())
    monkeypatch.setattr(
        "pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs", RuntimeParam
    )
    monkeypatch.setattr(
        "pulumi_datarobot.CustomModelRuntimeParameterValueArgs", RuntimeParam
    )
    monkeypatch.setattr("pulumi.export", MagicMock())
    monkeypatch.setattr("pulumi.info", MagicMock())
    monkeypatch.setattr("pulumi.warn", MagicMock())
    monkeypatch.setattr("pulumi.error", MagicMock())

    from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments

    patcher = patch.object(
        RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.__class__,
        "id",
        new_callable=PropertyMock,
        return_value="python-311-genai-agents-id",
    )
    patcher.start()

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

    yield
    patcher.stop()
    loop.close()
    asyncio.set_event_loop(None)


def _workload_module(monkeypatch, *, stub_ensure_entrypoint=True):
    """Import infra.agent_infra.workload with the pulumi_datarobot
    Artifact/Workload/ExecutionEnvironment resources stubbed out.

    Pass ``stub_ensure_entrypoint=False`` to keep the real
    ``_ensure_agent_has_entrypoint`` in place.

    No reload needed: workload.py has no env-dependent module-level constants
    (all env reads happen inside functions), unlike deployment.py's HA-mode ones.
    """
    import infra.agent_infra.workload as workload

    # Stubbed by default: most tests aim the application path at an empty tmp_path,
    # which has no pyproject.toml for the real thing to read.
    if stub_ensure_entrypoint:
        monkeypatch.setattr(workload, "_ensure_agent_has_entrypoint", MagicMock())

    # _fake_resource so the real pulumi.ResourceOptions(depends_on=[...])
    # validation (which requires actual Resource instances) accepts these stubs.
    mock_workload_instance = _fake_resource(
        endpoint=FakeOutput("https://workload.example.com/"),
        id=FakeOutput("workload-123"),
        artifact_id=FakeOutput("artifact-123"),
    )
    monkeypatch.setattr(
        workload.pulumi_datarobot,
        "Workload",
        MagicMock(return_value=mock_workload_instance),
    )

    mock_artifact_instance = _fake_resource(artifact_id="mock-artifact-id")
    monkeypatch.setattr(
        workload.pulumi_datarobot,
        "Artifact",
        MagicMock(return_value=mock_artifact_instance),
    )
    monkeypatch.setattr(
        workload.pulumi_datarobot,
        "ExecutionEnvironment",
        MagicMock(return_value=_fake_resource(id="ee-id", version_id="ee-version-id")),
    )
    monkeypatch.setattr(workload, "export", MagicMock())

    return workload


def _artifact_kwargs(workload):
    """Keyword arguments of the most recent ``pulumi_datarobot.Artifact`` call."""
    _, kwargs = workload.pulumi_datarobot.Artifact.call_args
    return kwargs


def _artifact_container(workload):
    """The single container spec of the most recent ``Artifact`` call."""
    return _artifact_kwargs(workload)["spec"].container_groups[0].containers[0]


class TestExplicitWorkloadEntrypoint:
    def test_unset_returns_none(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        assert workload._explicit_workload_entrypoint() is None

    def test_json_list(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", '["sh", "run_server.sh"]')
        assert workload._explicit_workload_entrypoint() == ["sh", "run_server.sh"]

    def test_comma_separated(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", "sh, run_server.sh")
        assert workload._explicit_workload_entrypoint() == ["sh", "run_server.sh"]

    def test_invalid_json_raises(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", "[not json")
        with pytest.raises(RuntimeError, match="not valid JSON"):
            workload._explicit_workload_entrypoint()

    def test_json_non_string_list_raises(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", "[1, 2]")
        with pytest.raises(RuntimeError, match="list of strings"):
            workload._explicit_workload_entrypoint()

    def test_resolve_generated_entrypoint_default(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        assert workload._resolve_generated_entrypoint() == [
            "sh",
            "workload/run_server.sh",
        ]

    def test_resolve_generated_entrypoint_override(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", "custom-entrypoint.sh")
        assert workload._resolve_generated_entrypoint() == ["custom-entrypoint.sh"]


class TestResolveContainerPortAndReadinessProbe:
    def test_default_port(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        assert workload._resolve_container_port() == 8080

    def test_override_port(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_CONTAINER_PORT", "9090")
        assert workload._resolve_container_port() == 9090

    def test_readiness_probe_uses_resolved_port(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_CONTAINER_PORT", "9090")
        probe = workload._readiness_probe()
        assert probe.path == "/health"
        assert probe.port == 9090


class TestImageUriArtifactArgs:
    """The pre-built-image artifact spec is assembled here in workload.py."""

    def _container(self, workload, **overrides):
        api_key_var = workload.pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            source="api-key"
        )
        workload._create_image_uri_artifact(
            **{
                "asset_name": "agent-artifact",
                "image_uri": "registry.example.com/agent:latest",
                "environment_vars": [api_key_var],
                "entrypoints": None,
                **overrides,
            }
        )
        return _artifact_kwargs(workload), _artifact_container(workload)

    def test_payload_shape(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        args, container = self._container(workload)
        assert args["name"] == "agent-artifact"
        assert args["type"] == "agent"
        assert args["spec"].a2a_enabled is True
        assert container.name == workload.WORKLOAD_CONTAINER_NAME
        assert container.primary is True
        assert container.port == 8080
        assert container.image_uri == "registry.example.com/agent:latest"
        assert [var.source for var in container.environment_vars] == ["api-key"]
        assert container.readiness_probe.path == "/health"

    def test_routes_omitted_by_default(self, monkeypatch):
        """Omitted, not `[]`: a cluster with route configuration disabled rejects
        an artifact that carries the key at all (403 "Route configuration is
        disabled on this cluster")."""
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(
            workload.base,
            "IS_A2A_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENABLED",
            False,
        )
        _, container = self._container(workload)
        assert container.routes is None

    def test_routes_include_well_known_when_enabled(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(
            workload.base,
            "IS_A2A_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENABLED",
            True,
        )
        _, container = self._container(workload)
        assert len(container.routes) == 1
        assert container.routes[0].path == "/a2a/.well-known/agent-card.json"
        assert container.routes[0].auth == "optional"

    def test_entrypoints_omitted_when_unset(self, monkeypatch):
        """Omitting the key keeps the image's own CMD/entrypoint."""
        workload = _workload_module(monkeypatch)
        _, container = self._container(workload)
        assert container.entrypoints is None

    def test_entrypoints_included_when_set(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        _, container = self._container(workload, entrypoints=["python", "main.py"])
        assert container.entrypoints == ["python", "main.py"]

    def test_port_override_applies_to_container_and_probe(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_CONTAINER_PORT", "9090")
        _, container = self._container(workload)
        assert container.port == 9090
        assert container.readiness_probe.port == 9090


def _workload_module_unstubbed():
    """workload.py with nothing stubbed out.

    Enough for the pure env-reading helpers, which build plain spec args and
    touch no Pulumi resource, so these tests do not depend on which artifact
    collaborators the module happens to expose.
    """
    import infra.agent_infra.workload as workload

    return workload


class TestOtelEndpointEnvVar:
    """OTEL_EXPORTER_OTLP_ENDPOINT reaches the container only when set locally."""

    def test_empty_when_unset(self, monkeypatch):
        workload = _workload_module_unstubbed()
        assert workload._otel_endpoint_env_var() == []

    def test_endpoint_forwarded_when_set(self, monkeypatch):
        workload = _workload_module_unstubbed()
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "https://app.datarobot.com/otel"
        )
        env_vars = workload._otel_endpoint_env_var()
        assert len(env_vars) == 1
        assert env_vars[0].name == "OTEL_EXPORTER_OTLP_ENDPOINT"
        assert env_vars[0].value == "https://app.datarobot.com/otel"

    def test_surrounding_whitespace_stripped(self, monkeypatch):
        workload = _workload_module_unstubbed()
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "  https://app.datarobot.com/otel  "
        )
        assert (
            workload._otel_endpoint_env_var()[0].value
            == "https://app.datarobot.com/otel"
        )

    def test_blank_value_is_not_forwarded(self, monkeypatch):
        workload = _workload_module_unstubbed()
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   ")
        assert workload._otel_endpoint_env_var() == []

    def test_lands_in_container_env_vars_before_runtime_params(self, monkeypatch):
        workload = _workload_module_unstubbed()
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "https://app.datarobot.com/otel"
        )
        params = [RuntimeParam(key="LLM_DEPLOYMENT_ID", type="string", value="dep-1")]
        names = [
            getattr(var, "name", None)
            for var in workload._workload_environment_vars(params)
        ]
        assert names == [
            None,  # source="api-key"
            "WORKLOAD_CONTAINER_PORT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "LLM_DEPLOYMENT_ID",
        ]

    def test_omitted_from_container_env_vars_when_unset(self, monkeypatch):
        workload = _workload_module_unstubbed()
        names = [
            getattr(var, "name", None)
            for var in workload._workload_environment_vars([])
        ]
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in names


class TestRuntimeParamEnvVars:
    def test_credential_type_becomes_dr_credential(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        params = [
            RuntimeParam(key="SESSION_SECRET_KEY", type="credential", value="cred-id")
        ]
        env_vars = workload._runtime_param_env_vars(params)
        assert len(env_vars) == 1
        assert env_vars[0].name == "SESSION_SECRET_KEY"
        assert env_vars[0].source == "dr-credential"
        assert env_vars[0].dr_credential_id == "cred-id"
        assert env_vars[0].key == "apiToken"

    def test_other_types_become_plain_value(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        params = [
            RuntimeParam(
                key="AGENT_GUNICORN_WORKER_TIMEOUT", type="string", value="600"
            )
        ]
        env_vars = workload._runtime_param_env_vars(params)
        assert len(env_vars) == 1
        assert env_vars[0].name == "AGENT_GUNICORN_WORKER_TIMEOUT"
        assert env_vars[0].value == "600"

    def test_workload_environment_vars_leads_with_api_key_source(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        env_vars = workload._workload_environment_vars([])
        assert env_vars[0].source == "api-key"
        assert env_vars[0].name is None

    def test_workload_environment_vars_excludes_nothing_extra(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        params = [RuntimeParam(key="LLM_DEPLOYMENT_ID", type="string", value="dep-1")]
        env_vars = workload._workload_environment_vars(params)
        assert len(env_vars) == 3
        assert env_vars[1].name == "WORKLOAD_CONTAINER_PORT"
        assert env_vars[1].value == "8080"
        assert env_vars[2].name == "LLM_DEPLOYMENT_ID"
        assert env_vars[2].value == "dep-1"

    def test_workload_environment_vars_injects_resolved_port(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv("WORKLOAD_CONTAINER_PORT", "9090")
        env_vars = workload._workload_environment_vars([])
        assert env_vars[1].name == "WORKLOAD_CONTAINER_PORT"
        assert env_vars[1].value == "9090"


class TestProvisionWorkloadAgentRequiredEnv:
    def test_missing_api_token_raises(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.delenv("DATAROBOT_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="DATAROBOT_API_TOKEN"):
            workload.provision_workload_agent([])


class TestProvisionWorkloadAgentImageUriScenario:
    def test_selected_when_image_uri_set(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )

        result = workload.provision_workload_agent([])

        workload.pulumi_datarobot.Artifact.assert_called_once()
        container = _artifact_container(workload)
        assert container.image_uri == "registry.example.com/agent:latest"
        assert container.readiness_probe.path == "/health"
        assert container.readiness_probe.port == 8080
        assert container.environment_vars[0].source == "api-key"
        workload.pulumi_datarobot.Workload.assert_called_once()
        assert result["execution_environment"] is None
        assert result["deployment"] is None
        assert result["workload"] is not None

    def test_exports_use_asset_name_convention(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        workload.pulumi.export.reset_mock()

        workload.provision_workload_agent([])

        export_names = [call.args[0] for call in workload.pulumi.export.call_args_list]
        asset_name = "[unittest] [agent]"
        assert "Agent Workload Endpoint " + asset_name in export_names
        assert "Agent Workload Id " + asset_name in export_names
        assert "Agent Workload Artifact Id " + asset_name in export_names
        assert "Agent Workload Image URI " + asset_name in export_names
        assert "Agent Workload Chat Endpoint " + asset_name in export_names

    def test_disk_exports_workload_id(self, monkeypatch):
        from unittest.mock import ANY

        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        workload.export.reset_mock()

        workload.provision_workload_agent([])

        workload.export.assert_any_call(
            "AGENT_WORKLOAD_ID",
            ANY,
        )

    def test_does_not_touch_custom_models_resources(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        monkeypatch.setattr("pulumi_datarobot.CustomModel", MagicMock())
        monkeypatch.setattr("pulumi_datarobot.Playground", MagicMock())
        monkeypatch.setattr("pulumi_datarobot.LlmBlueprint", MagicMock())

        workload.provision_workload_agent([])

        workload.pulumi_datarobot.CustomModel.assert_not_called()
        workload.pulumi_datarobot.Playground.assert_not_called()
        workload.pulumi_datarobot.LlmBlueprint.assert_not_called()

    def test_entrypoint_override_passed_through(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        monkeypatch.setenv("WORKLOAD_ENTRYPOINT", '["python", "main.py"]')

        workload.provision_workload_agent([])

        assert _artifact_container(workload).entrypoints == ["python", "main.py"]


class TestEnsureAgentHasEntrypoint:
    """Nothing installs the agent inside the C2W image, so it resolves the workflow
    through a `.dist-info` generated here from pyproject.toml and uploaded with the
    source.
    """

    PYPROJECT = """\
[project]
name = "agent"
version = "0.1.0"

[project.entry-points.'nat.plugins']
base_agent = "agent.register"
"""

    @staticmethod
    def _write_pyproject(application_path, body):
        (application_path / "pyproject.toml").write_text(body, encoding="utf-8")

    def test_writes_dist_info_from_pyproject(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(tmp_path, self.PYPROJECT)

        workload._ensure_agent_has_entrypoint(tmp_path)

        dist_info = tmp_path / "agent-0.1.0.dist-info"
        assert (dist_info / "entry_points.txt").read_text() == (
            "[nat.plugins]\nbase_agent = agent.register\n"
        )
        metadata = (dist_info / "METADATA").read_text()
        assert "Name: agent" in metadata and "Version: 0.1.0" in metadata

    def test_is_byte_stable_across_runs(self, monkeypatch, tmp_path):
        """Churning bytes here would change the source hash and force a rebuild."""
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(tmp_path, self.PYPROJECT)
        entry_points = tmp_path / "agent-0.1.0.dist-info" / "entry_points.txt"

        workload._ensure_agent_has_entrypoint(tmp_path)
        first = entry_points.read_bytes()
        workload._ensure_agent_has_entrypoint(tmp_path)

        assert entry_points.read_bytes() == first

    def test_tracks_pyproject_changes(self, monkeypatch, tmp_path):
        """Regenerated every deploy, so an edited entry point cannot go stale."""
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(tmp_path, self.PYPROJECT)
        workload._ensure_agent_has_entrypoint(tmp_path)

        self._write_pyproject(
            tmp_path, self.PYPROJECT.replace("base_agent", "renamed_agent")
        )
        workload._ensure_agent_has_entrypoint(tmp_path)

        entry_points = (
            tmp_path / "agent-0.1.0.dist-info" / "entry_points.txt"
        ).read_text()
        assert "renamed_agent = agent.register" in entry_points

    def test_removes_dist_info_from_a_previous_version(self, monkeypatch, tmp_path):
        """Two same-named distributions on sys.path resolve unpredictably."""
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        stale = tmp_path / "agent-0.0.9.dist-info"
        stale.mkdir()
        (stale / "entry_points.txt").write_text("[nat.plugins]\nold = agent.old\n")
        self._write_pyproject(tmp_path, self.PYPROJECT)

        workload._ensure_agent_has_entrypoint(tmp_path)

        assert not stale.exists()
        assert (tmp_path / "agent-0.1.0.dist-info").is_dir()

    def test_keeps_all_declared_entry_point_groups(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(
            tmp_path,
            self.PYPROJECT
            + "\n[project.entry-points.'other.group']\nx = \"agent.x\"\n",
        )

        workload._ensure_agent_has_entrypoint(tmp_path)

        body = (tmp_path / "agent-0.1.0.dist-info" / "entry_points.txt").read_text()
        assert "[nat.plugins]" in body and "[other.group]" in body

    def test_raises_when_no_nat_entry_point_declared(self, monkeypatch, tmp_path):
        """Not recoverable: only pyproject.toml can say what the workflow module is."""
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(
            tmp_path,
            '[project]\nname = "agent"\nversion = "0.1.0"\n'
            "\n[project.entry-points.'console_scripts']\nfoo = \"agent.cli:main\"\n",
        )

        with pytest.raises(RuntimeError, match="nat.plugins"):
            workload._ensure_agent_has_entrypoint(tmp_path)

    def test_raises_when_pyproject_missing(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)

        with pytest.raises(RuntimeError, match="pyproject.toml"):
            workload._ensure_agent_has_entrypoint(tmp_path)

    def test_raises_when_pyproject_is_malformed(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch, stub_ensure_entrypoint=False)
        self._write_pyproject(tmp_path, "[project\nname = ")

        with pytest.raises(RuntimeError, match="pyproject.toml"):
            workload._ensure_agent_has_entrypoint(tmp_path)


class TestProvisionWorkloadAgentSourceBundleScenarios:
    def test_generated_dockerfile_ensures_entrypoint(self, monkeypatch, tmp_path):
        """Only this scenario uploads source and imports the agent out of it."""
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)

        workload.provision_workload_agent([])

        workload._ensure_agent_has_entrypoint.assert_called_once_with(tmp_path)

    def test_prebuilt_image_skips_entrypoint_check(self, monkeypatch, tmp_path):
        """Nothing is uploaded there, so local metadata is irrelevant."""
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )

        workload.provision_workload_agent([])

        workload._ensure_agent_has_entrypoint.assert_not_called()

    def test_generated_dockerfile_scenario(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)

        result = workload.provision_workload_agent([])

        workload.pulumi_datarobot.Artifact.assert_called_once()
        assert _artifact_kwargs(workload)["source"].dir == str(tmp_path)
        dockerfile = _artifact_container(workload).image_build_config.dockerfile
        assert dockerfile.source == "generated"
        assert dockerfile.entrypoints == ["sh", "workload/run_server.sh"]
        workload.pulumi_datarobot.ExecutionEnvironment.assert_called_once()
        _, ee_kwargs = workload.pulumi_datarobot.ExecutionEnvironment.call_args
        assert ee_kwargs["use_cases"] == ["customModel"]
        assert result["execution_environment"] is not None

    def test_generated_dockerfile_exports_execution_environment_ids(
        self, monkeypatch, tmp_path
    ):
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)
        workload.pulumi.export.reset_mock()

        workload.provision_workload_agent([])

        export_names = [call.args[0] for call in workload.pulumi.export.call_args_list]
        asset_name = "[unittest] [agent]"
        assert "Agent Execution Environment ID " + asset_name in export_names
        assert "Agent Execution Environment Version ID " + asset_name in export_names

    def test_does_not_touch_custom_models_resources(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)
        monkeypatch.setattr("pulumi_datarobot.CustomModel", MagicMock())
        monkeypatch.setattr("pulumi_datarobot.Playground", MagicMock())
        monkeypatch.setattr("pulumi_datarobot.LlmBlueprint", MagicMock())

        result = workload.provision_workload_agent([])

        workload.pulumi_datarobot.CustomModel.assert_not_called()
        workload.pulumi_datarobot.Playground.assert_not_called()
        workload.pulumi_datarobot.LlmBlueprint.assert_not_called()
        assert result["deployment"] is None

    def test_readiness_probe_threaded_into_image_artifact(self, monkeypatch, tmp_path):
        workload = _workload_module(monkeypatch)
        monkeypatch.setattr(workload.base, "agent_application_path", tmp_path)
        monkeypatch.setenv("WORKLOAD_CONTAINER_PORT", "9090")

        workload.provision_workload_agent([])

        readiness_probe = _artifact_container(workload).readiness_probe
        assert readiness_probe.path == "/health"
        assert readiness_probe.port == 9090


class TestProvisionWorkloadAgentExports:
    def test_a2a_endpoint_present_when_enabled(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        monkeypatch.setattr(workload.base, "IS_A2A_SERVER_ENABLED", True)

        result = workload.provision_workload_agent([])

        assert result["agent_a2a_endpoint"] == FakeOutput(
            "https://workload.example.com/a2a/"
        )
        param_keys = [p.key for p in result["agent_runtime_parameters"]]
        assert "AGENT_A2A_ENDPOINT" in param_keys

    def test_a2a_endpoint_absent_when_disabled(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )
        monkeypatch.setattr(workload.base, "IS_A2A_SERVER_ENABLED", False)

        result = workload.provision_workload_agent([])

        assert result["agent_a2a_endpoint"] is None
        param_keys = [p.key for p in result["agent_runtime_parameters"]]
        assert "AGENT_A2A_ENDPOINT" not in param_keys

    def test_completions_endpoint_format(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )

        result = workload.provision_workload_agent([])

        assert result["agent_serving_endpoint"] == FakeOutput(
            "https://workload.example.com/chat/completions"
        )

    def test_runtime_parameter_keys(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        monkeypatch.setenv(
            "WORKLOAD_AGENT_IMAGE_URI", "registry.example.com/agent:latest"
        )

        result = workload.provision_workload_agent([])

        app_keys = {p.key for p in result["app_runtime_parameters"]}
        agent_keys = {p.key for p in result["agent_runtime_parameters"]}
        assert app_keys == {
            "AGENT_WORKLOAD_ID",
            "AGENT_ENDPOINT",
        }
        assert agent_keys == {
            "AGENT_WORKLOAD_ID",
            "AGENT_ENDPOINT",
        }


class TestWorkloadArtifactRoutes:
    def _opt_in(self, monkeypatch, workload, enabled):
        monkeypatch.setattr(
            workload.base,
            "IS_A2A_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENABLED",
            enabled,
        )

    def test_none_when_disabled(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        self._opt_in(monkeypatch, workload, False)
        assert workload._workload_artifact_routes() is None

    def test_well_known_route_when_enabled(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        self._opt_in(monkeypatch, workload, True)
        routes = workload._workload_artifact_routes()
        assert len(routes) == 1
        assert routes[0].path == "/a2a/.well-known/agent-card.json"
        assert routes[0].auth == "optional"

    def test_generated_image_artifact_omits_routes_by_default(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        self._opt_in(monkeypatch, workload, False)
        workload.provision_workload_agent([])
        assert _artifact_container(workload).routes is None

    def test_well_known_route_passed_to_generated_image_artifact(self, monkeypatch):
        workload = _workload_module(monkeypatch)
        self._opt_in(monkeypatch, workload, True)
        workload.provision_workload_agent([])
        routes = _artifact_container(workload).routes
        assert len(routes) == 1
        assert routes[0].path == "/a2a/.well-known/agent-card.json"
        assert routes[0].auth == "optional"
