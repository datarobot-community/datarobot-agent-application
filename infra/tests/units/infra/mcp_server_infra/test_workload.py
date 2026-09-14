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
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar
from unittest.mock import ANY, MagicMock, Mock, patch

import pulumi_datarobot
import pytest

from infra.mcp_server_infra import workload
from infra.mcp_server_infra.mcp_utils import (
    DR_CREDENTIAL_API_TOKEN_KEY,
    InfraProviderOutput,
    MCPRuntimeParameter,
    MCPRuntimeParameterAPITokenCredential,
    PulumiOutputEndpoints,
)
from infra.mcp_server_infra.workload import (
    WorkloadBuilder,
    WorkloadConfiguration,
    WorkloadGeneratedDockerfileManager,
    WorkloadProvidedDockerfileManager,
    WorkloadProvider,
)

# Bound to a name so call sites stay a fixed width: this file is a copier
# template and the app name inside the label varies in length, which otherwise
# makes `ruff format --check` pass or fail depending on the rendered name.
ASSET_NAME = "[unittest] [mcp_server]"


class MockOutput(MagicMock):
    def __init__(self, val=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply = MagicMock(side_effect=lambda fn, v=val: fn(v))


@contextmanager
def env(**variables: str | None):
    """Temporarily set or remove environment variables."""
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


@contextmanager
def pulumi_stubs():
    export = MagicMock()
    with (
        patch.object(workload.pulumi, "export", export),
        patch.object(workload.pulumi, "info", MagicMock()),
        patch.object(workload.pulumi, "error", MagicMock()),
    ):
        yield {"export": export}


def _catalog() -> MagicMock:
    catalog = MagicMock()
    catalog.catalog_id = "cat-id"
    catalog.catalog_version_id = "ver-id"
    return catalog


@pytest.fixture
def artifact_kwargs() -> dict:
    return {
        "mcp_server_asset_name": "srv",
        "workload_api_endpoint": "https://api",
        "catalog": _catalog(),
        "bundle_hash": "hash",
        "environment_vars": [],
        "routes": None,
        "build_timeout_s": 6000,
    }


@contextmanager
def stub_provision(*, dockerfile: str | None):
    artifact = MagicMock(artifact_id="art-id")
    wl = MagicMock(endpoint=MockOutput("https://host/"))
    with (
        env(DATAROBOT_ENDPOINT="https://api", DATAROBOT_API_TOKEN="tok"),
        patch.object(
            workload, "_resolve_dockerfile_relative_path", return_value=dockerfile
        ),
        patch.object(workload, "get_workload_source_files", return_value=[("/a", "a")]),
        patch.object(workload, "source_bundle_hash", return_value="hash"),
        patch.object(workload, "FilesCatalogBundle", return_value=_catalog()),
        patch.object(
            workload, "_create_workload_image_artifact", return_value=artifact
        ),
        patch.object(workload, "_create_workload", return_value=wl),
        patch.object(
            workload,
            "_export_workload_endpoints",
            return_value=PulumiOutputEndpoints(
                base_endpoint="https://host/", mcp_endpoint="https://host/mcp"
            ),
        ),
        pulumi_stubs(),
    ):
        yield wl


class TestRequireEnv:
    def test_returns_value_when_set(self) -> None:
        with env(SOME_REQUIRED_ENV=" value "):
            assert workload._require_env("SOME_REQUIRED_ENV") == "value"

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_raises_when_missing_or_blank(self, value: str | None) -> None:
        with (
            env(SOME_REQUIRED_ENV=value),
            pytest.raises(RuntimeError, match="SOME_REQUIRED_ENV is required"),
        ):
            workload._require_env("SOME_REQUIRED_ENV")


class TestWorkloadEntrypoint:
    def test_none_when_unset(self) -> None:
        with env(MCP_WORKLOAD_ENTRYPOINT=None):
            assert workload._explicit_workload_entrypoint() is None

    def test_json_list(self) -> None:
        with env(MCP_WORKLOAD_ENTRYPOINT='["python", "-m", "app.main"]'):
            assert workload._explicit_workload_entrypoint() == [
                "python",
                "-m",
                "app.main",
            ]

    def test_comma_separated(self) -> None:
        with env(MCP_WORKLOAD_ENTRYPOINT="python, -m , app.main"):
            assert workload._explicit_workload_entrypoint() == [
                "python",
                "-m",
                "app.main",
            ]

    def test_invalid_json_raises(self) -> None:
        with (
            env(MCP_WORKLOAD_ENTRYPOINT='["python",'),
            pytest.raises(RuntimeError, match="not valid JSON"),
        ):
            workload._explicit_workload_entrypoint()

    def test_json_non_string_list_raises(self) -> None:
        with (
            env(MCP_WORKLOAD_ENTRYPOINT="[1, 2]"),
            pytest.raises(RuntimeError, match="list of strings"),
        ):
            workload._explicit_workload_entrypoint()

    def test_resolve_falls_back_to_default(self) -> None:
        with env(MCP_WORKLOAD_ENTRYPOINT=None):
            assert (
                workload._resolve_workload_entrypoint() == workload.DEFAULT_ENTRYPOINT
            )

    def test_resolve_uses_explicit_value(self) -> None:
        with env(MCP_WORKLOAD_ENTRYPOINT="python,app.main"):
            expected = ["python", "app.main"]
            actual = workload._resolve_workload_entrypoint()
            assert actual == expected


class TestUserParamEnvVars:
    def test_string_params_become_uppercased_env_vars(self) -> None:
        credential_params = [
            MCPRuntimeParameterAPITokenCredential(
                name="my_secret", value="credential-id"
            ),
        ]
        params = [
            MCPRuntimeParameter(name="user_name", type="string", value="alice"),
        ]
        with (
            patch.object(
                workload, "MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS", credential_params
            ),
            patch.object(workload, "MCP_USER_RUNTIME_PARAMETERS", params),
        ):
            actual = workload.user_param_env_vars()

            assert actual[0]["name"] == "USER_NAME"
            assert actual[1]["name"] == "MY_SECRET"

    def test_credential_params_become_dr_credential_references(self) -> None:
        credential_params = [
            MCPRuntimeParameterAPITokenCredential(
                name="my_secret", value="credential-raw-value"
            ),
        ]
        mock_pulumi_output = Mock(id="some-id")
        mock_api_token_credential_cls = MagicMock(return_value=mock_pulumi_output)
        with (
            patch.object(
                workload, "MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS", credential_params
            ),
            patch.object(workload, "MCP_USER_RUNTIME_PARAMETERS", []),
            patch.object(
                pulumi_datarobot, "ApiTokenCredential", mock_api_token_credential_cls
            ),
        ):
            actual = workload.user_param_env_vars()

        mock_api_token_credential_cls.assert_called_once()
        assert actual == [
            {
                "name": "MY_SECRET",
                "source": "dr-credential",
                "drCredentialId": mock_pulumi_output.id,
                "key": DR_CREDENTIAL_API_TOKEN_KEY,
            },
        ]

    def test_user_params_included_in_workload_environment_vars(self) -> None:
        credential_params = [
            MCPRuntimeParameterAPITokenCredential(
                name="my_secret", value="credential-id"
            ),
        ]
        params = [
            MCPRuntimeParameter(name="user_name", type="string", value="alice"),
        ]
        with (
            env(MCP_SERVER_NAME=None, SESSION_SECRET_KEY=None),
            patch.object(
                workload, "MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS", credential_params
            ),
            patch.object(workload, "MCP_USER_RUNTIME_PARAMETERS", params),
        ):
            env_vars = workload._workload_environment_vars(ASSET_NAME)

        assert {"name": "USER_NAME", "value": "alice", "source": "string"} in env_vars
        assert {"name": "MCP_SERVER_NAME", "value": "datarobot-mcp-server"} in env_vars
        assert "AUTH_RESOLUTION_STRATEGY" in {entry["name"] for entry in env_vars}


class TestSessionSecretEnvVars:
    def test_empty_when_unset(self) -> None:
        with env(SESSION_SECRET_KEY=None):
            assert workload._session_secret_env_vars(ASSET_NAME) == []

    def test_creates_dr_credential_reference(self) -> None:
        with env(SESSION_SECRET_KEY="super-secret"):
            entries = workload._session_secret_env_vars(ASSET_NAME)

        assert len(entries) == 1
        entry = entries[0]
        assert entry["name"] == "SESSION_SECRET_KEY"
        assert entry["source"] == "dr-credential"
        assert entry["key"] == DR_CREDENTIAL_API_TOKEN_KEY
        assert "super-secret" not in str(entry.get("value", ""))


class TestResolveContainerPort:
    def test_default_port(self) -> None:
        with env(MCP_WORKLOAD_CONTAINER_PORT=None):
            expected = 8080
            actual = workload._resolve_container_port()
            assert actual == expected

    def test_custom_port(self) -> None:
        with env(MCP_WORKLOAD_CONTAINER_PORT="9000"):
            expected = 9000
            actual = workload._resolve_container_port()
            assert actual == expected


class TestResolveDockerfileRelativePath:
    @pytest.mark.parametrize("value", ["none", "false", "0", "NONE"])
    def test_disabled_values_return_none(self, value: str) -> None:
        with env(MCP_WORKLOAD_DOCKERFILE_PATH=value):
            expected = None
            actual = workload._resolve_dockerfile_relative_path()
            assert actual == expected

    def test_explicit_path(self) -> None:
        with env(MCP_WORKLOAD_DOCKERFILE_PATH="custom/Dockerfile"):
            expected = "custom/Dockerfile"
            actual = workload._resolve_dockerfile_relative_path()
            assert actual == expected

    def test_returns_none_when_default_dockerfile_missing(self, tmp_path) -> None:
        project_dir = tmp_path / "infra" / "infra"
        with (
            patch.object(workload, "project_dir", project_dir),
            env(MCP_WORKLOAD_DOCKERFILE_PATH=None),
        ):
            expected = None
            actual = workload._resolve_dockerfile_relative_path()
            assert actual == expected

    def test_returns_default_when_dockerfile_exists(self, tmp_path) -> None:
        project_dir = tmp_path / "infra" / "infra"
        docker_dir = tmp_path / "infra" / "mcp_server"
        docker_dir.mkdir(parents=True)
        (docker_dir / "Dockerfile").write_text("FROM scratch\n")
        with (
            patch.object(workload, "project_dir", project_dir),
            env(MCP_WORKLOAD_DOCKERFILE_PATH=None),
        ):
            expected = "Dockerfile"
            actual = workload._resolve_dockerfile_relative_path()
            assert actual == expected


class TestDeploymentsApplicationPath:
    def test_points_to_mcp_server_sibling(self, tmp_path) -> None:
        project_dir = tmp_path / "infra" / "infra"
        project_dir.mkdir(parents=True)
        with patch.object(workload, "project_dir", project_dir):
            expected = tmp_path / "infra" / "mcp_server"
            actual = workload._deployments_application_path()
            assert actual == expected


class TestWorkloadConstants:
    def test_default_entrypoint(self) -> None:
        expected = ["python", "-m", "app.main"]
        actual = workload.DEFAULT_ENTRYPOINT
        assert actual == expected

    def test_container_name(self) -> None:
        expected = "mcp-server"
        actual = workload.WORKLOAD_CONTAINER_NAME
        assert actual == expected

    def test_default_memory_bytes(self) -> None:
        expected = 512 * 1024 * 1024
        actual = workload.DEFAULT_WORKLOAD_MEMORY_BYTES
        assert actual == expected


class TestWorkloadEnvironmentVars:
    #: Settings the deployment path injects as runtime parameters, with the
    #: defaults it uses — the workload path must not silently drop any of them.
    DEPLOYMENT_PARITY_DEFAULTS: ClassVar[dict[str, str]] = {
        "MCP_SERVER_LOG_LEVEL": "WARNING",
        "APP_LOG_LEVEL": "INFO",
        "MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR": "warn",
        "MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA": "false",
        "MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR": "warn",
        "OTEL_ATTRIBUTES": "{}",
        "OTEL_ENABLED": "true",
        "OTEL_ENABLED_HTTP_INSTRUMENTORS": "false",
        "MCP_ENABLE_OAUTH_CLAIM_VALIDATION": "false",
    }

    def test_claim_validation_is_forwarded_when_on(self) -> None:
        with env(
            SESSION_SECRET_KEY=None,
            MCP_ENABLE_OAUTH_CLAIM_VALIDATION="true",
            MCP_XAA_TOKEN_AUDIENCE="https://mcp.example.com",
        ):
            forwarded = {
                v["name"]: v["value"]
                for v in workload._workload_environment_vars("[test]")
                if v.get("source") not in {"credential", "dr-credential"}
            }

        assert forwarded["MCP_ENABLE_OAUTH_CLAIM_VALIDATION"] == "true"
        assert forwarded["MCP_XAA_TOKEN_AUDIENCE"] == "https://mcp.example.com"

    def test_custom_mcp_server_name(self) -> None:
        with env(MCP_SERVER_NAME="my-mcp", SESSION_SECRET_KEY=None):
            env_vars = workload._workload_environment_vars("[test]")
            actual = next(v for v in env_vars if v["name"] == "MCP_SERVER_NAME")
            expected = {"name": "MCP_SERVER_NAME", "value": "my-mcp"}
            assert actual == expected

    def test_deployment_path_settings_ride_along_with_their_defaults(self) -> None:
        unset = {name: None for name in self.DEPLOYMENT_PARITY_DEFAULTS}
        with env(
            SESSION_SECRET_KEY=None,
            OTEL_COLLECTOR_BASE_URL=None,
            OTEL_ENTITY_ID=None,
            **unset,
        ):
            forwarded = {
                v["name"]: v["value"]
                for v in workload._workload_environment_vars("[test]")
                if v.get("source") not in {"credential", "dr-credential"}
            }

        for name, default in self.DEPLOYMENT_PARITY_DEFAULTS.items():
            assert forwarded[name] == default
        # Optional OTEL settings stay absent when unset, as on the deployment path.
        assert "OTEL_COLLECTOR_BASE_URL" not in forwarded
        assert "OTEL_ENTITY_ID" not in forwarded

    def test_configured_values_are_forwarded_and_normalized(self) -> None:
        with env(
            SESSION_SECRET_KEY=None,
            MCP_SERVER_LOG_LEVEL="DEBUG",
            MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR="ERROR",
            OTEL_ENABLED="FALSE",
            OTEL_COLLECTOR_BASE_URL="https://collector",
            OTEL_ENTITY_ID="deployment-123",
        ):
            forwarded = {
                v["name"]: v["value"]
                for v in workload._workload_environment_vars("[test]")
                if v.get("source") not in {"credential", "dr-credential"}
            }

        assert forwarded["MCP_SERVER_LOG_LEVEL"] == "DEBUG"
        assert forwarded["MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR"] == "error"
        assert forwarded["OTEL_ENABLED"] == "false"
        assert forwarded["OTEL_COLLECTOR_BASE_URL"] == "https://collector"
        assert forwarded["OTEL_ENTITY_ID"] == "deployment-123"


class TestCreateWorkload:
    def test_uses_high_importance_by_default(self) -> None:
        mock = MagicMock()
        with (
            patch.object(workload.pulumi_datarobot, "Workload", mock),
            env(MCP_WORKLOAD_IMPORTANCE=None),
        ):
            workload._create_workload(
                mcp_server_asset_name="srv", artifact_id="art-id", depends_on=[]
            )
        actual = mock.call_args.kwargs["importance"]
        expected = "high"
        assert actual == expected

    def test_runtime_uses_env_overrides(self) -> None:
        mock = MagicMock()
        with (
            patch.object(workload.pulumi_datarobot, "Workload", mock),
            env(
                MCP_WORKLOAD_REPLICA_COUNT="3",
                MCP_WORKLOAD_CPU="2.5",
                MCP_WORKLOAD_MEMORY="1200",
            ),
        ):
            workload._create_workload(
                mcp_server_asset_name="srv", artifact_id="art-id", depends_on=[]
            )
        container = mock.call_args.kwargs["runtime"].container_groups[0].containers[0]
        actual = container.resource_allocation

        expected = {"cpu": 2.5, "memory": "1200"}
        assert actual.cpu == expected["cpu"]
        assert actual.memory == expected["memory"]


class TestExportWorkloadEndpoints:
    def test_mcp_endpoint_appends_suffix(self) -> None:
        endpoint = Mock(apply=lambda fn: fn("https://host/"))
        wl = Mock(endpoint=endpoint)

        with pulumi_stubs():
            actual = workload._export_workload_endpoints("srv", wl)

        expected = PulumiOutputEndpoints(
            base_endpoint=endpoint, mcp_endpoint="https://host/mcp"
        )
        assert actual == expected

    def test_exports_workload_metadata(self) -> None:
        wl = MagicMock(
            endpoint=MockOutput("https://host/"), id="w1", name="srv", artifact_id="a1"
        )
        with pulumi_stubs() as stubs:
            workload._export_workload_endpoints("srv", wl)
            actual = {call.args[0] for call in stubs["export"].call_args_list}
        expected = {
            "srv Workload Endpoint",
            "srv Workload Id",
            "srv Workload Name",
            "srv Workload Artifact Id",
        }
        assert expected <= actual

    def test_every_export_is_namespaced_by_asset_name(self) -> None:
        """This component is `repeatable`; bare names would collide between servers."""
        wl = MagicMock(
            endpoint=MockOutput("https://host/"), id="w1", name="srv", artifact_id="a1"
        )
        with pulumi_stubs() as stubs:
            workload._export_workload_endpoints("srv", wl)
            names = [call.args[0] for call in stubs["export"].call_args_list]
        actual = [name for name in names if not name.startswith("srv ")]
        expected: list[str] = []
        assert actual == expected


class TestCreateWorkloadImageArtifact:
    def test_uses_provided_dockerfile_path(self, artifact_kwargs: dict) -> None:
        mock_cls = MagicMock()
        with (
            patch.object(workload, "WorkloadImageArtifact", mock_cls),
            patch.object(workload.pulumi, "ResourceOptions", MagicMock()),
        ):
            workload._create_workload_image_artifact(
                **artifact_kwargs,
                dockerfile_relative_path="Dockerfile",
                execution_environment=None,
            )
        actual = mock_cls.call_args.kwargs["dockerfile_relative_path"]
        expected = "Dockerfile"
        assert actual == expected

    def test_uses_generated_dockerfile(self, artifact_kwargs: dict) -> None:
        mock_cls = MagicMock()
        ee = MagicMock(id="ee-id", version_id="ee-ver")
        with (
            patch.object(workload, "WorkloadGeneratedImageArtifact", mock_cls),
            patch.object(workload.pulumi, "ResourceOptions", MagicMock()),
        ):
            workload._create_workload_image_artifact(
                **artifact_kwargs,
                dockerfile_relative_path=None,
                execution_environment=ee,
            )
        actual = mock_cls.call_args.kwargs["execution_environment_id"]
        expected = "ee-id"
        assert actual == expected

    def test_raises_without_execution_environment(self, artifact_kwargs: dict) -> None:
        with (
            patch.object(workload.pulumi, "error", MagicMock()),
            pytest.raises(RuntimeError, match="execution environment is required"),
        ):
            workload._create_workload_image_artifact(
                **artifact_kwargs,
                dockerfile_relative_path=None,
                execution_environment=None,
            )


class TestProvisionWorkloadMcpServer:
    def test_returns_mcp_endpoint_with_provided_dockerfile(self) -> None:
        with stub_provision(dockerfile="Dockerfile"):
            actual = workload.provision_workload_mcp_server(
                mcp_server_asset_name="srv", get_deployments_app_files=list
            )["mcp_server_mcp_endpoint"]
        expected = "https://host/mcp"
        assert actual == expected

    def test_provisions_execution_environment_for_generated_dockerfile(self) -> None:
        ee = MagicMock(id="ee-id", version_id="ee-ver")
        with (
            stub_provision(dockerfile=None),
            patch.object(
                workload, "provision_mcp_execution_environment", return_value=ee
            ),
        ):
            actual = workload.provision_workload_mcp_server(
                mcp_server_asset_name="srv", get_deployments_app_files=list
            )["execution_environment"]
        expected = ee
        assert actual == expected

    def test_raises_without_api_token(self) -> None:
        with (
            env(DATAROBOT_ENDPOINT="https://api", DATAROBOT_API_TOKEN=None),
            pytest.raises(RuntimeError, match="DATAROBOT_API_TOKEN is required"),
        ):
            workload.provision_workload_mcp_server(
                mcp_server_asset_name="srv", get_deployments_app_files=list
            )


class TestProvisionWorkloadMcpServerFromImageUri:
    def test_returns_mcp_endpoint(self) -> None:
        spec = MagicMock()
        spec.to_pulumi_args.return_value = {"type": "service"}
        artifact = MagicMock(artifact_id="art-id")
        wl = MagicMock(endpoint=MockOutput("https://host/"))
        with (
            patch.object(workload, "build_artifact_from_image_uri", return_value=spec),
            patch.object(workload.pulumi_datarobot, "Artifact", return_value=artifact),
            patch.object(workload, "_create_workload", return_value=wl),
            patch.object(
                workload,
                "_export_workload_endpoints",
                return_value=PulumiOutputEndpoints(
                    base_endpoint="https://host/", mcp_endpoint="https://host/mcp"
                ),
            ),
            pulumi_stubs(),
        ):
            actual = workload.provision_workload_mcp_server_from_image_uri(
                mcp_server_asset_name="srv", workload_image_uri="img:tag"
            )["mcp_server_mcp_endpoint"]
        expected = "https://host/mcp"
        assert actual == expected

    def test_exports_workload_image_uri(self) -> None:
        spec = MagicMock(to_pulumi_args=MagicMock(return_value={"type": "service"}))
        artifact = MagicMock(artifact_id="art-id")
        base_endpoint = "https://host/"
        wl = MagicMock(endpoint=MockOutput(base_endpoint))
        endpoints = PulumiOutputEndpoints(
            base_endpoint=base_endpoint, mcp_endpoint=base_endpoint + "mcp"
        )
        with (
            patch.object(workload, "build_artifact_from_image_uri", return_value=spec),
            patch.object(workload.pulumi_datarobot, "Artifact", return_value=artifact),
            patch.object(workload, "_create_workload", return_value=wl),
            patch.object(
                workload, "_export_workload_endpoints", return_value=endpoints
            ),
            pulumi_stubs() as stubs,
        ):
            workload.provision_workload_mcp_server_from_image_uri(
                mcp_server_asset_name="srv", workload_image_uri="img:tag"
            )
            actual = stubs["export"].call_args_list[0].args
        expected = ("srv Workload Image URI", "img:tag")
        assert actual == expected


class TestWorkloadProvider:
    @pytest.fixture
    def mock_workload_manager(self):
        manager = Mock()
        return manager

    def test_call_provision_mcp_server_from_workload_manager(
        self, mock_workload_manager
    ):
        provider = WorkloadProvider(mock_workload_manager)

        provider.provision_mcp_server()

        mock_workload_manager.provision_mcp_server.assert_called_once()

    def test_provision_mcp_server_return(self, mock_workload_manager):
        infra_provider_output = InfraProviderOutput(
            execution_environment="execution_environment",
            deployment="deployment",
            mcp_server_mcp_endpoint="deployment_endpoints/mcp",
            mcp_server_base_endpoint="deployment_endpoints",
            mcp_custom_model_runtime_parameters=[],
        )
        mock_workload_manager.provision_mcp_server.return_value = infra_provider_output
        provider = WorkloadProvider(mock_workload_manager)

        actual = provider.provision_mcp_server()

        expected = infra_provider_output
        assert actual == expected


@pytest.mark.usefixtures("mock_require_env")
class TestWorkloadProvidedDockerfileManager:
    @pytest.fixture
    def mock_require_env(self):
        with patch.object(
            workload,
            "_require_env",
            return_value="configured",
        ) as require_env:
            yield require_env

    @pytest.fixture
    def mock_file_bundler(self, tmp_path):
        file_bundler = Mock()
        file_bundler.setup_dir_for_artifact_provided_dockerfile.return_value = (
            tmp_path / ".build"
        )
        return file_bundler

    @pytest.fixture
    def mock_workload_builder(self):
        builder = Mock()
        builder.build_workload_from_image_build_config.return_value = Mock()
        yield builder

    def test_call_provision_mcp_server(self, mock_file_bundler, mock_workload_builder):
        workload_manager = WorkloadProvidedDockerfileManager(
            "mcp_name", Path("Dockerfile"), mock_file_bundler, mock_workload_builder
        )

        workload_manager.provision_mcp_server()

    def test_provision_mcp_server_return(
        self, mock_file_bundler, mock_workload_builder
    ):
        workload_manager = WorkloadProvidedDockerfileManager(
            "mcp_name", Path("Dockerfile"), mock_file_bundler, mock_workload_builder
        )

        actual = workload_manager.provision_mcp_server()

        expected = InfraProviderOutput(
            execution_environment=None,
            deployment=None,
            mcp_server_mcp_endpoint=ANY,
            mcp_server_base_endpoint=ANY,
            mcp_custom_model_runtime_parameters=[],
        )
        assert actual == expected


@pytest.mark.usefixtures("mock_require_env")
class TestWorkloadGeneratedDockerfileManager:
    @pytest.fixture
    def mock_require_env(self):
        with patch.object(
            workload,
            "_require_env",
            return_value="configured",
        ) as require_env:
            yield require_env

    @pytest.fixture
    def mock_file_bundler(self, tmp_path):
        file_bundler = Mock()
        file_bundler.setup_dir_for_artifact_provided_dockerfile.return_value = (
            tmp_path / ".build"
        )
        return file_bundler

    @pytest.fixture
    def mock_workload_result(self):
        workload = Mock(
            spec=pulumi_datarobot.Workload(
                "resource_name", artifact_id="aid123", runtime=Mock()
            )
        )
        workload.endpoint = Mock()
        workload.id = "wid123"
        workload.name = "name"
        yield workload

    @pytest.fixture
    def mock_workload_builder(self, mock_workload_result):
        builder = Mock()
        builder.build_from_artifact_image_build_config.return_value = (
            mock_workload_result
        )
        yield builder

    @pytest.fixture
    def mock_execution_env(self):
        exec_env = Mock(spec=pulumi_datarobot.ExecutionEnvironment)
        yield exec_env

    def test_call_provision_mcp_server(
        self, mock_file_bundler, mock_execution_env, mock_workload_builder
    ):
        workload_manager = WorkloadGeneratedDockerfileManager(
            "mcp_name", mock_execution_env, mock_file_bundler, mock_workload_builder
        )

        workload_manager.provision_mcp_server()

    def test_provision_mcp_server_return(
        self, mock_file_bundler, mock_execution_env, mock_workload_builder
    ):
        workload_manager = WorkloadGeneratedDockerfileManager(
            "mcp_name", mock_execution_env, mock_file_bundler, mock_workload_builder
        )

        actual = workload_manager.provision_mcp_server()

        expected = InfraProviderOutput(
            execution_environment=mock_execution_env,
            deployment=None,
            mcp_server_mcp_endpoint=ANY,
            mcp_server_base_endpoint=ANY,
            mcp_custom_model_runtime_parameters=[],
        )
        assert actual == expected


@pytest.mark.usefixtures("mock_workload_cls", "mock_artifact_cls")
class TestWorkloadBuilder:
    @pytest.fixture
    def mock_artifact_cls(self):
        artifact = Mock(spec=pulumi_datarobot.Artifact)
        artifact.artifact_id = "art-id"
        with patch.object(
            workload.pulumi_datarobot, "Artifact", return_value=artifact
        ) as mock_cls:
            yield mock_cls

    @pytest.fixture
    def mock_workload_cls(self):
        wl = Mock(endpoint="https://host/", id="wid", artifact_id="art-id")
        # 'name' attribute is protected in Mock obj, so we explicitly need to set it
        # to avoid assert issues
        wl.name = "mcp_name"
        with patch.object(
            workload.pulumi_datarobot, "Workload", return_value=wl
        ) as mock_cls:
            yield mock_cls

    def test_build_from_artifact_image_build_config_calls_artifact_and_workload_once(
        self, mock_artifact_cls, mock_workload_cls
    ):
        builder = WorkloadBuilder("mcp_name", WorkloadConfiguration())

        builder.build_from_artifact_image_build_config(
            "artifact-name", "/tmp/src", Mock()
        )

        mock_artifact_cls.assert_called_once()
        mock_workload_cls.assert_called_once()

    def test_uses_provided_dockerfile_image_build_config(self, mock_artifact_cls):
        builder = WorkloadBuilder("mcp_name", WorkloadConfiguration())
        provided_dockerfile_image_build_config = pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs(
            source="provided", path="Dockerfile"
        )

        builder.build_from_artifact_image_build_config(
            "artifact-name", "/tmp/src", provided_dockerfile_image_build_config
        )
        spec = mock_artifact_cls.call_args.kwargs["spec"]
        actual = spec.container_groups[0].containers[0].image_build_config.dockerfile

        assert actual is provided_dockerfile_image_build_config

    def test_uses_generated_dockerfile_image_build_config(self, mock_artifact_cls):
        builder = WorkloadBuilder("mcp_name", WorkloadConfiguration())
        generated_dockerfile_image_build_config = pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs(
            source="generated",
            execution_environment_id="ee-id",
            execution_environment_version_id="ee-ver",
        )

        builder.build_from_artifact_image_build_config(
            "artifact-name", "/tmp/src", generated_dockerfile_image_build_config
        )
        spec = mock_artifact_cls.call_args.kwargs["spec"]
        actual = spec.container_groups[0].containers[0].image_build_config.dockerfile

        assert actual is generated_dockerfile_image_build_config
