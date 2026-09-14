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

"""MCP server provisioning via DataRobot Workload API + Pulumi."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, cast

import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

# The trailing commas below are load-bearing: this file is a copier template and
# the package prefix grows with the user's app name. A magic trailing comma keeps
# ruff from collapsing these onto one line for a short name and then re-wrapping
# them for a long one, which made `ruff format --check` fail per app name.
from mcp_server_clients.files_catalog_pulumi import (
    FilesCatalogBundle,
    source_bundle_hash,
)
from mcp_server_clients.workload_api_client import (
    build_artifact_from_image_uri,
)
from mcp_server_clients.workload_artifact_pulumi import (
    WorkloadGeneratedImageArtifact,
    WorkloadImageArtifact,
)

from .. import project_dir
from ..mcp_server_user_params import (
    MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS,
    MCP_USER_RUNTIME_PARAMETERS,
)
from .mcp_api_keys import (
    SESSION_SECRET_KEY,
    auth_resolution_strategy,
    dr_credential_env_var,
    workload_credential_env_vars,
)
from .mcp_bundle import (
    FileBundler,
    get_workload_source_files,
)
from .mcp_cli_configs import tool_flag_env_vars
from .mcp_execution_environment import provision_mcp_execution_environment
from .mcp_oauth_configs import (
    WorkloadArtifactContainerRoute,
    get_workload_mcp_oauth_routes,
    mcp_oauth_metadata_env_vars,
    mcp_tag_scope_env_vars,
    oauth_and_well_known_env_vars,
)
from .mcp_utils import (
    DR_CREDENTIAL_API_TOKEN_KEY,
    InfraProviderOutput,
    MCPAppEnvironmentVarNames,
    MCPRuntimeParameter,
    MCPRuntimeParameterAPITokenCredential,
    PulumiOutputEndpoints,
)

WORKLOAD_CONTAINER_NAME = "mcp-server"
DEFAULT_WORKLOAD_CONTAINER_PORT = 8080
DEFAULT_DOCKERFILE_RELATIVE_PATH = "Dockerfile"
DEFAULT_BUILD_TIMEOUT_S = 6000
DEFAULT_ENTRYPOINT = ["python", "-m", "app.main"]
DEFAULT_WORKLOAD_MEMORY_BYTES = 512 * 1024 * 1024  # 512 MiB in bytes


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        message = f"{name} is required for MCP_DEPLOYMENT_TYPE 'datarobot-workload' or 'datarobot-workload-preview'"
        pulumi.error(message)
        raise RuntimeError(message)
    return value


def _deployments_application_path() -> Path:
    return project_dir.parent / "mcp_server"


def _resolve_dockerfile_relative_path() -> str | None:
    """
    Return a catalog-relative Dockerfile path when using DockerfileProvided.

    ``MCP_WORKLOAD_DOCKERFILE_PATH`` overrides the default ``Dockerfile``
    check. Set ``MCP_WORKLOAD_DOCKERFILE_PATH=none`` (or ``false``/``0``) to force
    generated mode.
    """
    explicit = os.getenv("MCP_WORKLOAD_DOCKERFILE_PATH", "").strip()
    if explicit.lower() in {"none", "false", "0"}:
        return None
    if explicit:
        return explicit

    default_path = _deployments_application_path() / DEFAULT_DOCKERFILE_RELATIVE_PATH
    if default_path.is_file():
        return DEFAULT_DOCKERFILE_RELATIVE_PATH
    return None


def _explicit_workload_entrypoint() -> list[str] | None:
    """Parse MCP_WORKLOAD_ENTRYPOINT (JSON list or comma-separated); None when unset."""
    raw = os.getenv("MCP_WORKLOAD_ENTRYPOINT", "").strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            message = f"MCP_WORKLOAD_ENTRYPOINT is not valid JSON: {exc}"
            pulumi.error(message)
            raise RuntimeError(message) from exc
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            message = "MCP_WORKLOAD_ENTRYPOINT JSON must be a list of strings"
            pulumi.error(message)
            raise RuntimeError(message)
        return parsed
    return [part.strip() for part in raw.split(",") if part.strip()]


def _resolve_workload_entrypoint() -> list[str]:
    return _explicit_workload_entrypoint() or list(DEFAULT_ENTRYPOINT)


def _resolve_container_port() -> int:
    return int(
        os.getenv("MCP_WORKLOAD_CONTAINER_PORT", str(DEFAULT_WORKLOAD_CONTAINER_PORT))
    )


def user_param_env_vars() -> list[dict[str, str]]:
    """Map MCP_USER_RUNTIME_PARAMETERS (see mcp_server_user_params.py) onto container env vars.

    This mirrors the datarobot-serverless path, where the same list is injected
    as custom model runtime parameters. Credential-type parameters (whose value
    is an api-token DataRobot credential ID) become "dr-credential" env var
    references that the platform resolves at runtime.
    """
    env_vars: list[dict[str, str]] = []
    for param in MCP_USER_RUNTIME_PARAMETERS:
        # Values are pulumi Inputs; they are resolved before the dynamic
        # provider posts the payload, and pulumi_datarobot.Artifact accepts
        # them directly.
        env_vars.append(
            {
                "name": str(param.name).upper(),
                "value": cast(str, param.value),
                "source": "string",
            }
        )
    for el in MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS:
        api_token_credential = pulumi_datarobot.ApiTokenCredential(
            f"[{PROJECT_NAME}] {el.name}",
            args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=el.value),
        )
        env_vars.append(
            dr_credential_env_var(str(el.name).upper(), api_token_credential.id)
        )
    return env_vars


def _session_secret_env_vars(mcp_server_asset_name: str) -> list[dict[str, str]]:
    """Session secret injected via a DataRobot credential, mirroring deployment."""
    session_secret_key = os.getenv(SESSION_SECRET_KEY)
    if not session_secret_key:
        return []
    credential = pulumi_datarobot.ApiTokenCredential(
        mcp_server_asset_name + " Session Secret Key",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=session_secret_key),
    )
    return [dr_credential_env_var(SESSION_SECRET_KEY, credential.id)]


def _workload_environment_vars(mcp_server_asset_name: str) -> list[dict[str, str]]:
    """Container env vars for the workload, mirroring the deployment path.

    Every setting ``provision_deployment_mcp_server`` injects as a runtime
    parameter must ride along here too, with the same defaults — otherwise
    flipping MCP_DEPLOYMENT_TYPE to the workload preview silently drops
    configured logging, registration and OTEL behavior.
    """
    env_vars: list[dict[str, str]] = [
        {
            "name": "MCP_SERVER_NAME",
            "value": os.getenv("MCP_SERVER_NAME", "datarobot-mcp-server"),
        },
        {
            "name": "MCP_SERVER_LOG_LEVEL",
            "value": os.getenv("MCP_SERVER_LOG_LEVEL", "WARNING"),
        },
        {"name": "APP_LOG_LEVEL", "value": os.getenv("APP_LOG_LEVEL", "INFO")},
        {
            "name": "MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR",
            "value": str(
                os.getenv("MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR", "warn")
            ).lower(),
        },
        {
            "name": "MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA",
            "value": str(
                os.getenv("MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA", "false")
            ).lower(),
        },
        {
            "name": "MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR",
            "value": str(
                os.getenv("MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR", "warn")
            ).lower(),
        },
        {"name": "OTEL_ATTRIBUTES", "value": os.getenv("OTEL_ATTRIBUTES", "{}")},
        {
            "name": "OTEL_ENABLED",
            "value": str(os.getenv("OTEL_ENABLED", "true")).lower(),
        },
        {
            "name": "OTEL_ENABLED_HTTP_INSTRUMENTORS",
            "value": str(os.getenv("OTEL_ENABLED_HTTP_INSTRUMENTORS", "false")).lower(),
        },
        {"name": "AUTH_RESOLUTION_STRATEGY", "value": auth_resolution_strategy()},
        *tool_flag_env_vars(),
        *oauth_and_well_known_env_vars(),
        *user_param_env_vars(),
        *workload_credential_env_vars(),
        *_session_secret_env_vars(mcp_server_asset_name),
    ]
    # The optional OTEL settings ride along only when configured, as on the
    # deployment path.
    if otel_collector_base_url := os.getenv("OTEL_COLLECTOR_BASE_URL"):
        env_vars.append(
            {"name": "OTEL_COLLECTOR_BASE_URL", "value": otel_collector_base_url}
        )
    if otel_entity_id := os.getenv("OTEL_ENTITY_ID"):
        env_vars.append({"name": "OTEL_ENTITY_ID", "value": otel_entity_id})
    return env_vars


def _create_workload(
    *,
    mcp_server_asset_name: str,
    artifact_id: pulumi.Input[str],
    depends_on: list[Any],
) -> pulumi_datarobot.Workload:
    return pulumi_datarobot.Workload(  # type: ignore[call-overload]
        mcp_server_asset_name + " Workload",
        name=mcp_server_asset_name,
        artifact_id=artifact_id,
        importance=os.getenv("MCP_WORKLOAD_IMPORTANCE", "high"),
        runtime=pulumi_datarobot.WorkloadRuntimeArgs(
            container_groups=[
                pulumi_datarobot.WorkloadRuntimeContainerGroupArgs(
                    replica_count=int(os.getenv("MCP_WORKLOAD_REPLICA_COUNT", "1")),
                    containers=[
                        pulumi_datarobot.WorkloadRuntimeContainerGroupContainerArgs(
                            name=WORKLOAD_CONTAINER_NAME,
                            resource_allocation=pulumi_datarobot.WorkloadRuntimeContainerGroupContainerResourceAllocationArgs(
                                cpu=float(os.getenv("MCP_WORKLOAD_CPU", "1")),
                                memory=str(
                                    int(
                                        os.getenv(
                                            "MCP_WORKLOAD_MEMORY",
                                            str(DEFAULT_WORKLOAD_MEMORY_BYTES),
                                        )
                                    )
                                ),
                            ),
                        ),
                    ],
                ),
            ],
        ),
        opts=pulumi.ResourceOptions(
            depends_on=depends_on,
            delete_before_replace=False,
            retain_on_delete=False,
        ),
    )


def _export_workload_endpoints(
    mcp_server_asset_name: str, workload: pulumi_datarobot.Workload
) -> PulumiOutputEndpoints:
    # Every export is prefixed with the asset name: this component is
    # `repeatable`, so a project may hold more than one MCP server and bare
    # names would collide between them (the deployment path does the same).
    pulumi.export(mcp_server_asset_name + " Workload Endpoint", workload.endpoint)
    pulumi.export(mcp_server_asset_name + " Workload Id", workload.id)
    pulumi.export(mcp_server_asset_name + " Workload Name", workload.name)
    pulumi.export(mcp_server_asset_name + " Workload Artifact Id", workload.artifact_id)
    mcp_workload_endpoint = workload.endpoint.apply(
        lambda endpoint: f"{endpoint.rstrip('/')}/mcp"
    )
    pulumi.export(
        mcp_server_asset_name + " MCP Server MCP Endpoint", mcp_workload_endpoint
    )
    pulumi.export(
        mcp_server_asset_name + " MCP Server Base Endpoint", workload.endpoint
    )
    return PulumiOutputEndpoints(
        mcp_endpoint=mcp_workload_endpoint,
        base_endpoint=workload.endpoint,
    )


def _create_workload_image_artifact(
    *,
    mcp_server_asset_name: str,
    workload_api_endpoint: str,
    catalog: FilesCatalogBundle,
    bundle_hash: str,
    environment_vars: list[dict[str, str]],
    routes: list[WorkloadArtifactContainerRoute] | None,
    build_timeout_s: int,
    dockerfile_relative_path: str | None,
    execution_environment: pulumi_datarobot.ExecutionEnvironment | None,
) -> WorkloadImageArtifact | WorkloadGeneratedImageArtifact:
    routes_val = [r.to_dict() for r in routes] if routes else None
    if dockerfile_relative_path:
        pulumi.info(
            f"Workload image build: DockerfileProvided (path={dockerfile_relative_path})"
        )
        return WorkloadImageArtifact(
            mcp_server_asset_name + " Workload Artifact [Provided Dockerfile]",
            workload_api_endpoint=workload_api_endpoint,
            artifact_name=mcp_server_asset_name,
            catalog_id=catalog.catalog_id,
            catalog_version_id=catalog.catalog_version_id,
            dockerfile_relative_path=dockerfile_relative_path,
            container_name=WORKLOAD_CONTAINER_NAME,
            container_port=_resolve_container_port(),
            environment_vars=environment_vars,
            routes=routes_val,
            source_hash=bundle_hash,
            build_timeout_s=build_timeout_s,
            opts=pulumi.ResourceOptions(depends_on=[catalog]),
        )

    if execution_environment is None:
        message = (
            "Internal error: execution environment is required for "
            "DockerfileGenerated builds"
        )
        pulumi.error(message)
        raise RuntimeError(message)

    pulumi.info(
        "Workload image build: DockerfileGenerated "
        "(execution environment aligned with datarobot-serverless)"
    )
    return WorkloadGeneratedImageArtifact(
        mcp_server_asset_name + " Workload Artifact [Generated Dockerfile]",
        workload_api_endpoint=workload_api_endpoint,
        artifact_name=mcp_server_asset_name,
        catalog_id=catalog.catalog_id,
        catalog_version_id=catalog.catalog_version_id,
        execution_environment_id=execution_environment.id,
        execution_environment_version_id=execution_environment.version_id,
        entrypoint=_resolve_workload_entrypoint(),
        container_name=WORKLOAD_CONTAINER_NAME,
        container_port=_resolve_container_port(),
        environment_vars=environment_vars,
        routes=routes_val,
        source_hash=bundle_hash,
        build_timeout_s=build_timeout_s,
        opts=pulumi.ResourceOptions(depends_on=[catalog, execution_environment]),
    )


def provision_workload_mcp_server(
    *,
    mcp_server_asset_name: str,
    get_deployments_app_files: Callable[[], list[tuple[str, str]]],
) -> dict[str, Any]:
    pulumi.info(
        "MCP_DEPLOYMENT_TYPE='datarobot-workload-preview' -> provisioning via Workload API "
        "(Files catalog + image-build artifact + Workload)."
    )

    datarobot_endpoint = _require_env("DATAROBOT_ENDPOINT")
    # Fail fast; dynamic providers read the token from the environment so it is
    # never stored in Pulumi state.
    _require_env("DATAROBOT_API_TOKEN")

    dockerfile_relative_path = _resolve_dockerfile_relative_path()
    source_files = get_workload_source_files(
        deployments_path=_deployments_application_path(),
        dockerfile_relative_path=dockerfile_relative_path,
        get_core_app_files=get_deployments_app_files,
    )
    bundle_hash = source_bundle_hash(source_files)

    catalog = FilesCatalogBundle(
        mcp_server_asset_name + " Files Catalog Bundle",
        files_api_endpoint=datarobot_endpoint,
        source_files=source_files,
        source_hash=bundle_hash,
    )

    execution_environment: pulumi_datarobot.ExecutionEnvironment | None = None
    if dockerfile_relative_path is None:
        execution_environment = provision_mcp_execution_environment(
            mcp_server_asset_name,
            resource_name_suffix=" [Workload Generated Dockerfile]",
        )

    artifact = _create_workload_image_artifact(
        mcp_server_asset_name=mcp_server_asset_name,
        workload_api_endpoint=datarobot_endpoint,
        catalog=catalog,
        bundle_hash=bundle_hash,
        environment_vars=_workload_environment_vars(mcp_server_asset_name),
        routes=get_workload_mcp_oauth_routes(),
        build_timeout_s=int(
            os.getenv("MCP_WORKLOAD_BUILD_TIMEOUT_S", str(DEFAULT_BUILD_TIMEOUT_S))
        ),
        dockerfile_relative_path=dockerfile_relative_path,
        execution_environment=execution_environment,
    )

    workload_depends_on: list[Any] = [artifact]
    if execution_environment is not None:
        workload_depends_on.append(execution_environment)

    workload = _create_workload(
        mcp_server_asset_name=mcp_server_asset_name,
        artifact_id=artifact.artifact_id,
        depends_on=workload_depends_on,
    )

    pulumi.export(mcp_server_asset_name + " Files Catalog Id", catalog.catalog_id)
    pulumi.export(
        mcp_server_asset_name + " Files Catalog Version Id", catalog.catalog_version_id
    )
    if execution_environment is not None:
        pulumi.export(
            mcp_server_asset_name + " Workload Execution Environment Id",
            execution_environment.id,
        )
        pulumi.export(
            mcp_server_asset_name + " Workload Execution Environment Version Id",
            execution_environment.version_id,
        )
    mcp_workload_endpoints = _export_workload_endpoints(mcp_server_asset_name, workload)

    return {
        "execution_environment": execution_environment,
        "deployment": None,
        "mcp_server_mcp_endpoint": mcp_workload_endpoints.mcp_endpoint,
        "mcp_server_base_endpoint": mcp_workload_endpoints.base_endpoint,
        "mcp_custom_model_runtime_parameters": [],
    }


def provision_workload_mcp_server_from_image_uri(
    *,
    mcp_server_asset_name: str,
    workload_image_uri: str,
) -> dict[str, Any]:
    pulumi.info(
        "MCP_DEPLOYMENT_TYPE='datarobot-workload-preview' -> provisioning via Workload API "
        "(Workload image URI)."
    )

    routes_ = get_workload_mcp_oauth_routes()
    routes = [r.to_dict() for r in routes_] if routes_ else None
    workload_artifact_spec = build_artifact_from_image_uri(
        artifact_name=mcp_server_asset_name,
        container_name=WORKLOAD_CONTAINER_NAME,
        container_port=_resolve_container_port(),
        image_uri=workload_image_uri,
        environment_vars=_workload_environment_vars(mcp_server_asset_name),
        # Only override the image's own entrypoint when explicitly configured.
        entrypoints=_explicit_workload_entrypoint(),
        routes=routes,
    )

    artifact = pulumi_datarobot.Artifact(
        mcp_server_asset_name + " Workload Artifact [Image URI]",
        **workload_artifact_spec.to_pulumi_args(),
    )

    workload = _create_workload(
        mcp_server_asset_name=mcp_server_asset_name,
        artifact_id=artifact.artifact_id,
        depends_on=[artifact],
    )

    pulumi.export(mcp_server_asset_name + " Workload Image URI", workload_image_uri)
    mcp_workload_endpoints = _export_workload_endpoints(mcp_server_asset_name, workload)

    return {
        "execution_environment": None,
        "deployment": None,
        "mcp_server_mcp_endpoint": mcp_workload_endpoints.mcp_endpoint,
        "mcp_server_base_endpoint": mcp_workload_endpoints.base_endpoint,
        "mcp_custom_model_runtime_parameters": [],
    }


PROVIDED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS = (
    ".venv",
    ".git",
    ".gitignore",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "*.pyc",
    "tests",
    "test_interactive.py",
    ".coveragerc",
    ".pre-commit-config.yaml",
    ".licenserc.yaml",
    ".dockerignore",
    "pytest.ini",
    "AGENTS.md",
    "Taskfile.yaml",
)


GENERATED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS = (
    ".venv",
    ".git",
    ".gitignore",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "*.pyc",
    "tests",
    "test_interactive.py",
    ".coveragerc",
    ".pre-commit-config.yaml",
    ".licenserc.yaml",
    # "docker",
    "pytest.ini",
    "AGENTS.md",
    "Taskfile.yaml",
    "Dockerfile",
    ".dockerignore",
)


@dataclass
class WorkloadArtifactContainerDataRobotCredentialEnvVar:
    name: str
    dr_credential_id: str | pulumi.output.Output[str]
    key: str = DR_CREDENTIAL_API_TOKEN_KEY
    source: str = "dr-credential"

    def to_pulumi_object(
        self,
    ) -> pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs:
        return pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            source=self.source,
            name=self.name,
            dr_credential_id=self.dr_credential_id,
            key=self.key,
            value=None,
        )

    @classmethod
    def from_user_runtime_param(
        cls, runtime_param: MCPRuntimeParameterAPITokenCredential
    ) -> WorkloadArtifactContainerDataRobotCredentialEnvVar:
        api_token_credential = pulumi_datarobot.ApiTokenCredential(
            f"[{PROJECT_NAME}] {runtime_param.name}",
            args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=runtime_param.value),
        )
        return cls(
            name=runtime_param.name,
            dr_credential_id=api_token_credential.id,
            source="dr-credential"
            if runtime_param.type == "credential"
            else runtime_param.type,
            key=runtime_param.key,
        )


@dataclass
class WorkloadArtifactSpecContainerEnvVar:
    name: str
    value: str
    source: str = "string"

    def to_pulumi_object(
        self,
    ) -> pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs:
        return pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            source=self.source,
            name=self.name,
            value=self.value,
            dr_credential_id=None,
            key=None,
        )

    @classmethod
    def from_user_runtime_param(
        cls, runtime_param: MCPRuntimeParameter
    ) -> WorkloadArtifactSpecContainerEnvVar:
        return cls(
            name=runtime_param.name,
            value=runtime_param.value,
            source=runtime_param.type,
        )


@dataclass
class WorkloadContainerEnvironmentVars:
    session_secret_key: WorkloadArtifactContainerDataRobotCredentialEnvVar  # requires _session_secret_env_vars()
    mcp_server_name: str = "datarobot-mcp-server"
    mcp_server_log_level: str = "WARNING"
    app_log_level: str = "INFO"
    mcp_server_tool_registration_duplicate_behavior: str = "warn"
    mcp_server_tool_registration_allow_empty_schema: str = "false"
    mcp_server_prompt_registration_duplicate_behavior: str = "warn"
    otel_attributes: str = "{}"
    otel_enabled: str = "true"
    otel_enabled_http_instrumentors: str = "false"
    otel_collector_base_url: str | None = None  # drop it if None on the output
    otel_entity_id: str | None = None  # drop it if None on the output
    auth_resolution_strategy: str = (
        "http"  # requires func auth_resolution_strategy() to get value
    )
    _mcp_cli_configs: list[WorkloadArtifactSpecContainerEnvVar] = field(
        default_factory=list
    )  # requires func tool_flag_env_vars() to get value
    mcp_enable_unauthenticated_well_known_route: str = "false"
    mcp_enable_oauth_claim_validation: str = "false"
    _mcp_oauth_metadata: list[WorkloadArtifactSpecContainerEnvVar] = field(
        default_factory=list
    )  # requires func mcp_oauth_metadata_env_vars()
    _mcp_scopes: list[WorkloadArtifactSpecContainerEnvVar] = field(
        default_factory=list
    )  # requires func mcp_tag_scope_env_vars()
    _mcp_user_runtime_parameters: list[WorkloadArtifactSpecContainerEnvVar] = field(
        default_factory=list
    )
    _mcp_user_credential_runtime_parameters: list[
        WorkloadArtifactContainerDataRobotCredentialEnvVar
    ] = field(default_factory=list)
    _credential_env_vars: list[WorkloadArtifactContainerDataRobotCredentialEnvVar] = (
        field(default_factory=list)
    )  # requires func workload_credential_env_vars()

    @classmethod
    def from_os_env(
        cls, mcp_server_asset_name: str
    ) -> WorkloadContainerEnvironmentVars:
        def get_from_os(os_env_var_name: str, field_value: Any):
            return os.getenv(os_env_var_name, field_value)

        def get_strbool_from_os(os_env_var_name: str, field_value: Any) -> str:
            value = str(get_from_os(os_env_var_name, field_value))
            truthy_values = frozenset({"true", "1", "yes", "on"})
            return str(value.strip().lower() in truthy_values).lower()

        session_secret_key_list = _session_secret_env_vars(mcp_server_asset_name)
        if not session_secret_key_list:
            raise RuntimeError(
                "A SESSION_SECRET_KEY is required in your env for deployments."
            )
        session_secret_key_ = session_secret_key_list[0]
        session_secret_key = WorkloadArtifactContainerDataRobotCredentialEnvVar(
            name=session_secret_key_["name"],
            dr_credential_id=session_secret_key_["drCredentialId"],
        )

        return cls(
            mcp_server_name=get_from_os(
                MCPAppEnvironmentVarNames.MCP_SERVER_NAME.name, cls.mcp_server_name
            ),
            mcp_server_log_level=get_from_os(
                MCPAppEnvironmentVarNames.MCP_SERVER_LOG_LEVEL.name,
                cls.mcp_server_log_level,
            ),
            app_log_level=get_from_os(
                MCPAppEnvironmentVarNames.APP_LOG_LEVEL.name, cls.app_log_level
            ),
            mcp_server_tool_registration_duplicate_behavior=get_from_os(
                MCPAppEnvironmentVarNames.MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR.name,
                cls.mcp_server_tool_registration_duplicate_behavior,
            ),
            mcp_server_tool_registration_allow_empty_schema=get_from_os(
                MCPAppEnvironmentVarNames.MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA.name,
                cls.mcp_server_tool_registration_allow_empty_schema,
            ),
            mcp_server_prompt_registration_duplicate_behavior=get_from_os(
                MCPAppEnvironmentVarNames.MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR.name,
                cls.mcp_server_prompt_registration_duplicate_behavior,
            ),
            otel_attributes=get_from_os(
                MCPAppEnvironmentVarNames.OTEL_ATTRIBUTES.name, cls.otel_attributes
            ),
            otel_enabled=get_from_os(
                MCPAppEnvironmentVarNames.OTEL_ENABLED.name, cls.otel_enabled
            ),
            otel_enabled_http_instrumentors=get_from_os(
                MCPAppEnvironmentVarNames.OTEL_ENABLED_HTTP_INSTRUMENTORS.name,
                cls.otel_enabled_http_instrumentors,
            ),
            otel_collector_base_url=get_from_os(
                MCPAppEnvironmentVarNames.OTEL_COLLECTOR_BASE_URL.name,
                cls.otel_collector_base_url,
            ),
            otel_entity_id=get_from_os(
                MCPAppEnvironmentVarNames.OTEL_ENTITY_ID.name, cls.otel_entity_id
            ),
            auth_resolution_strategy=auth_resolution_strategy(),
            _mcp_cli_configs=[
                WorkloadArtifactSpecContainerEnvVar(el["name"], el["value"])
                for el in tool_flag_env_vars()
            ],
            mcp_enable_unauthenticated_well_known_route=get_strbool_from_os(
                MCPAppEnvironmentVarNames.MCP_ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE.name,
                cls.mcp_enable_unauthenticated_well_known_route,
            ),
            mcp_enable_oauth_claim_validation=get_strbool_from_os(
                MCPAppEnvironmentVarNames.MCP_ENABLE_OAUTH_CLAIM_VALIDATION.name,
                cls.mcp_enable_oauth_claim_validation,
            ),
            _mcp_oauth_metadata=[
                WorkloadArtifactSpecContainerEnvVar(el["name"], el["value"])
                for el in mcp_oauth_metadata_env_vars()
            ],
            _mcp_scopes=[
                WorkloadArtifactSpecContainerEnvVar(el["name"], el["value"])
                for el in mcp_tag_scope_env_vars()
            ],
            _mcp_user_runtime_parameters=[
                WorkloadArtifactSpecContainerEnvVar.from_user_runtime_param(el)
                for el in MCP_USER_RUNTIME_PARAMETERS
            ],
            _mcp_user_credential_runtime_parameters=[
                WorkloadArtifactContainerDataRobotCredentialEnvVar.from_user_runtime_param(
                    el
                )
                for el in MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS
            ],
            _credential_env_vars=[
                WorkloadArtifactContainerDataRobotCredentialEnvVar(
                    el["name"], el["drCredentialId"]
                )
                for el in workload_credential_env_vars()
            ],
            session_secret_key=session_secret_key,
        )

    def to_pulumi_objects(
        self,
    ) -> list[pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs]:
        def make_pulumi_obj(name: str, value: str):
            return (
                pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
                    source="string",
                    name=name.upper(),
                    value=value,
                    dr_credential_id=None,
                    key=None,
                )
            )

        env_var_pulumi_objects = [
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_SERVER_NAME.name, self.mcp_server_name
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_SERVER_LOG_LEVEL.name,
                self.mcp_server_log_level,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.APP_LOG_LEVEL.name, self.app_log_level
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR.name,
                self.mcp_server_tool_registration_duplicate_behavior,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA.name,
                self.mcp_server_tool_registration_allow_empty_schema,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR.name,
                self.mcp_server_prompt_registration_duplicate_behavior,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.OTEL_ATTRIBUTES.name, self.otel_attributes
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.OTEL_ENABLED.name, self.otel_enabled
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.OTEL_ENABLED_HTTP_INSTRUMENTORS.name,
                self.otel_enabled_http_instrumentors,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.AUTH_RESOLUTION_STRATEGY.name,
                self.auth_resolution_strategy,
            ),
            *[el.to_pulumi_object() for el in self._mcp_cli_configs],
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE.name,
                self.mcp_enable_unauthenticated_well_known_route,
            ),
            make_pulumi_obj(
                MCPAppEnvironmentVarNames.MCP_ENABLE_OAUTH_CLAIM_VALIDATION.name,
                self.mcp_enable_oauth_claim_validation,
            ),
            *[el.to_pulumi_object() for el in self._mcp_oauth_metadata],
            *[el.to_pulumi_object() for el in self._mcp_scopes],
            *[el.to_pulumi_object() for el in self._mcp_user_runtime_parameters],
            *[
                el.to_pulumi_object()
                for el in self._mcp_user_credential_runtime_parameters
            ],
            *[el.to_pulumi_object() for el in self._credential_env_vars],
            self.session_secret_key.to_pulumi_object(),
        ]
        if self.otel_collector_base_url:
            env_var_pulumi_objects.append(
                make_pulumi_obj(
                    MCPAppEnvironmentVarNames.OTEL_COLLECTOR_BASE_URL.name,
                    self.otel_collector_base_url,
                )
            )
        if self.otel_entity_id:
            env_var_pulumi_objects.append(
                make_pulumi_obj(
                    MCPAppEnvironmentVarNames.OTEL_ENTITY_ID.name, self.otel_entity_id
                )
            )

        return env_var_pulumi_objects


class WorkloadConfigurationEnvVars(Enum):
    MCP_WORKLOAD_IMPORTANCE = auto()
    MCP_WORKLOAD_ARTIFACT_STATUS = auto()
    MCP_WORKLOAD_CPU = auto()
    MCP_WORKLOAD_MEMORY = auto()
    MCP_WORKLOAD_REPLICA_COUNT = auto()
    MCP_WORKLOAD_CONTAINER_PORT = auto()


@dataclass
class WorkloadConfiguration:
    workload_importance: str = "high"
    artifact_type: str = "mcp"
    artifact_status: str = "locked"
    container_group_replica_count: int = 1
    container_cpu: float = 1.0
    container_memory: int = int(str(DEFAULT_WORKLOAD_MEMORY_BYTES))
    container_name: str = WORKLOAD_CONTAINER_NAME
    container_port: int = int(str(DEFAULT_WORKLOAD_CONTAINER_PORT))
    container_environment_variables: (
        list[pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs]
        | None
    ) = None
    container_routes: (
        list[pulumi_datarobot.ArtifactSpecContainerGroupContainerRouteArgs] | None
    ) = None

    @classmethod
    def from_os_env(cls, mcp_server_asset_name: str) -> WorkloadConfiguration:
        routes = get_workload_mcp_oauth_routes()
        return cls(
            workload_importance=os.getenv(
                WorkloadConfigurationEnvVars.MCP_WORKLOAD_IMPORTANCE.name,
                cls.workload_importance,
            ),
            artifact_type="mcp",
            artifact_status=os.getenv(
                WorkloadConfigurationEnvVars.MCP_WORKLOAD_ARTIFACT_STATUS.name,
                cls.artifact_status,
            ),
            container_group_replica_count=int(
                os.getenv(
                    WorkloadConfigurationEnvVars.MCP_WORKLOAD_REPLICA_COUNT.name,
                    cls.container_group_replica_count,
                )
            ),
            container_cpu=float(
                os.getenv(
                    WorkloadConfigurationEnvVars.MCP_WORKLOAD_CPU.name,
                    cls.container_cpu,
                )
            ),
            container_memory=int(
                os.getenv(
                    WorkloadConfigurationEnvVars.MCP_WORKLOAD_MEMORY.name,
                    cls.container_memory,
                )
            ),
            container_name=cls.container_name,
            container_port=int(
                os.getenv(
                    WorkloadConfigurationEnvVars.MCP_WORKLOAD_CONTAINER_PORT.name,
                    cls.container_port,
                )
            ),
            container_environment_variables=WorkloadContainerEnvironmentVars.from_os_env(
                mcp_server_asset_name
            ).to_pulumi_objects(),
            container_routes=(
                [el.to_pulumi_object() for el in routes] if routes else None
            ),
        )

    @classmethod
    def _explicit_workload_entrypoint(cls) -> list[str] | None:
        """Parse MCP_WORKLOAD_ENTRYPOINT (JSON list or comma-separated); None when unset."""
        raw = os.getenv("MCP_WORKLOAD_ENTRYPOINT", "").strip()
        if not raw:
            return None
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except ValueError as exc:
                message = f"MCP_WORKLOAD_ENTRYPOINT is not valid JSON: {exc}"
                pulumi.error(message)
                raise RuntimeError(message) from exc
            if not isinstance(parsed, list) or not all(
                isinstance(x, str) for x in parsed
            ):
                message = "MCP_WORKLOAD_ENTRYPOINT JSON must be a list of strings"
                pulumi.error(message)
                raise RuntimeError(message)
            return parsed
        return [part.strip() for part in raw.split(",") if part.strip()]

    @classmethod
    def resolve_workload_entrypoint(cls) -> list[str]:
        default_entrypoint = ["python", "-m", "app.main"]
        return cls._explicit_workload_entrypoint() or list(default_entrypoint)


class WorkloadBuilder:
    def __init__(
        self, mcp_server_asset_name: str, workload_config: WorkloadConfiguration
    ):
        self.mcp_server_asset_name = mcp_server_asset_name
        self._workload_config = workload_config

    def build_from_artifact_image_build_config(
        self,
        artifact_name: str,
        mcp_source_dir_abs_path: str,
        image_build_config: pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs,
    ) -> pulumi_datarobot.Workload:
        mcp_artifact = pulumi_datarobot.Artifact(
            artifact_name,
            name=artifact_name,
            description=f"MCP server artifact built for '{self.mcp_server_asset_name}'",
            type=self._workload_config.artifact_type,
            status=self._workload_config.artifact_status,
            source=pulumi_datarobot.ArtifactSourceArgs(dir=mcp_source_dir_abs_path),
            spec=pulumi_datarobot.ArtifactSpecArgs(
                container_groups=[
                    pulumi_datarobot.ArtifactSpecContainerGroupArgs(
                        containers=[
                            pulumi_datarobot.ArtifactSpecContainerGroupContainerArgs(
                                name=self._workload_config.container_name,
                                primary=True,
                                port=self._workload_config.container_port,
                                environment_vars=self._workload_config.container_environment_variables,
                                image_build_config=pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigArgs(
                                    dockerfile=image_build_config
                                ),
                                routes=self._workload_config.container_routes,
                            ),
                        ],
                    ),
                ],
            ),
        )

        workload = self._create_workload(mcp_artifact)
        return workload

    def _create_workload(
        self, artifact: pulumi_datarobot.Artifact
    ) -> pulumi_datarobot.Workload:
        workload_depends_on: list[pulumi_datarobot.Artifact] = [artifact]
        workload_name = self.mcp_server_asset_name + " Workload"

        workload = pulumi_datarobot.Workload(
            workload_name,
            name=self.mcp_server_asset_name,
            description="Workload serving the DataRobot MCP server artifact",
            importance=self._workload_config.workload_importance,
            artifact_id=artifact.artifact_id,
            runtime=pulumi_datarobot.WorkloadRuntimeArgs(
                container_groups=[
                    pulumi_datarobot.WorkloadRuntimeContainerGroupArgs(
                        replica_count=self._workload_config.container_group_replica_count,
                        containers=[
                            pulumi_datarobot.WorkloadRuntimeContainerGroupContainerArgs(
                                name=self._workload_config.container_name,
                                resource_allocation=pulumi_datarobot.WorkloadRuntimeContainerGroupContainerResourceAllocationArgs(
                                    cpu=self._workload_config.container_cpu,
                                    memory=str(self._workload_config.container_memory),
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            opts=pulumi.ResourceOptions(depends_on=workload_depends_on),
        )

        return workload

    def build_from_image_uri(
        self,
        artifact_name: str,
        image_uri: str,
    ):
        pass


class WorkloadGeneratedDockerfileManager:
    def __init__(
        self,
        mcp_server_asset_name: str,
        execution_environment: pulumi_datarobot.ExecutionEnvironment,
        file_bundler: FileBundler,
        workload_builder: WorkloadBuilder,
        workload_image_build_config_entrypoint: list[str] | None = None,
    ):
        self.mcp_server_asset_name = mcp_server_asset_name
        self.execution_environment = execution_environment
        self._ignore_files_patterns = GENERATED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS
        self._workload_image_build_config_dockerfile_source = "generated"
        self._file_bundler = file_bundler
        self._workload_builder = workload_builder
        self._workload_image_build_config_entrypoint = (
            workload_image_build_config_entrypoint
        )
        self._build_dir_relative_path = ".build/workload"

    def provision_mcp_server(self) -> InfraProviderOutput:
        pulumi.info(
            "MCP_DEPLOYMENT_TYPE='datarobot-workload' -> provisioning via Workload API "
            "(Workload API Generated Dockerfile)."
        )
        _require_env("DATAROBOT_ENDPOINT")
        # Fail fast; dynamic providers read the token from the environment so it is
        # never stored in Pulumi state.
        _require_env("DATAROBOT_API_TOKEN")

        build_dir_abs_path = self._file_bundler.get_workload_build_dir_abs_path(
            self._build_dir_relative_path, self.mcp_server_asset_name
        )
        staged_dir = (
            self._file_bundler.setup_build_dir_for_workload_artifact_source_dir(
                build_dir_abs_path, self._ignore_files_patterns
            )
        )
        mcp_dir = staged_dir.as_posix()
        pulumi.info(f"Files used to create MCP server can be found in: '{mcp_dir}'")

        # to show the type of image build configuration we are using
        pulumi.info(
            "Workload image build: DockerfileGenerated "
            "(execution environment aligned with datarobot-serverless)"
        )
        artifact_name = (
            self.mcp_server_asset_name + " Workload Artifact [Generated Dockerfile]"
        )
        image_build_config_dockerfile = pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs(
            source=self._workload_image_build_config_dockerfile_source,
            execution_environment_id=self.execution_environment.id,
            execution_environment_version_id=self.execution_environment.version_id,
            entrypoints=self._workload_image_build_config_entrypoint,
        )

        workload = self._workload_builder.build_from_artifact_image_build_config(
            artifact_name=artifact_name,
            mcp_source_dir_abs_path=mcp_dir,
            image_build_config=image_build_config_dockerfile,
        )

        pulumi.export(
            self.mcp_server_asset_name + " Workload Execution Environment Id",
            self.execution_environment.id,
        )
        pulumi.export(
            self.mcp_server_asset_name + " Workload Execution Environment Version Id",
            self.execution_environment.version_id,
        )

        mcp_workload_endpoints = _export_workload_endpoints(
            self.mcp_server_asset_name, workload
        )

        return InfraProviderOutput(
            execution_environment=self.execution_environment,
            deployment=None,
            mcp_server_mcp_endpoint=mcp_workload_endpoints.mcp_endpoint,
            mcp_server_base_endpoint=mcp_workload_endpoints.base_endpoint,
            mcp_custom_model_runtime_parameters=[],
        )


class WorkloadProvidedDockerfileManager:
    def __init__(
        self,
        mcp_server_asset_name: str,
        dockerfile_relative_path: str,
        file_bundler: FileBundler,
        workload_builder: WorkloadBuilder,
    ):
        self.mcp_server_asset_name = mcp_server_asset_name
        self.dockerfile_relative_path = dockerfile_relative_path
        self._workload_image_build_config_dockerfile_source = "provided"
        self._file_bundler = file_bundler
        self._workload_builder = workload_builder
        self._build_dir_relative_path = ".build/workload"
        self._ignore_files_patterns = PROVIDED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS

    def provision_mcp_server(self) -> InfraProviderOutput:
        pulumi.info(
            "MCP_DEPLOYMENT_TYPE='datarobot-workload' -> provisioning via Workload API "
            "(Workload API Provided Dockerfile)."
        )
        _require_env("DATAROBOT_ENDPOINT")
        # Fail fast; dynamic providers read the token from the environment so it is
        # never stored in Pulumi state.
        _require_env("DATAROBOT_API_TOKEN")

        build_dir_abs_path = self._file_bundler.get_workload_build_dir_abs_path(
            self._build_dir_relative_path, self.mcp_server_asset_name
        )
        staged_dir = (
            self._file_bundler.setup_build_dir_for_workload_artifact_source_dir(
                build_dir_abs_path, self._ignore_files_patterns
            )
        )
        mcp_dir = staged_dir.as_posix()
        pulumi.info(f"Files used to create MCP server can be found in: '{mcp_dir}'")

        # show the user the type of image build configuration we are using
        pulumi.info(
            f"Workload image build: DockerfileProvided (path={self.dockerfile_relative_path})"
        )
        artifact_name = (
            self.mcp_server_asset_name + " Workload Artifact [Provided Dockerfile]"
        )
        image_build_config_dockerfile = pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs(
            source=self._workload_image_build_config_dockerfile_source,
            path=self.dockerfile_relative_path,
        )

        workload = self._workload_builder.build_from_artifact_image_build_config(
            artifact_name, mcp_dir, image_build_config_dockerfile
        )

        mcp_workload_endpoints = _export_workload_endpoints(
            self.mcp_server_asset_name, workload
        )

        return InfraProviderOutput(
            execution_environment=None,
            deployment=None,
            mcp_server_mcp_endpoint=mcp_workload_endpoints.mcp_endpoint,
            mcp_server_base_endpoint=mcp_workload_endpoints.base_endpoint,
            mcp_custom_model_runtime_parameters=[],
        )


class WorkloadProvider:
    def __init__(
        self,
        workload_manager: WorkloadGeneratedDockerfileManager
        | WorkloadProvidedDockerfileManager,
    ):
        self.workload_manager = workload_manager

    def provision_mcp_server(self) -> InfraProviderOutput:
        mcp_outputs = self.workload_manager.provision_mcp_server()
        return mcp_outputs
