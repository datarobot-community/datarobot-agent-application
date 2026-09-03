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
from pathlib import Path
from typing import Any, cast

import pulumi
import pulumi_datarobot

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
from ..mcp_server_user_params import MCP_USER_RUNTIME_PARAMETERS
from .mcp_api_keys import (
    SESSION_SECRET_KEY,
    auth_resolution_strategy,
    dr_credential_env_var,
    workload_credential_env_vars,
)
from .mcp_bundle import get_workload_source_files
from .mcp_cli_configs import tool_flag_env_vars
from .mcp_execution_environment import provision_mcp_execution_environment
from .mcp_oauth_configs import (
    get_workload_mcp_oauth_routes,
    oauth_and_well_known_env_vars,
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
        message = (
            f"{name} is required for MCP_DEPLOYMENT_TYPE=datarobot-workload-preview"
        )
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
        if param.type == "credential":
            env_vars.append(dr_credential_env_var(str(param.key).upper(), param.value))
            continue
        # Values are pulumi Inputs; they are resolved before the dynamic
        # provider posts the payload, and pulumi_datarobot.Artifact accepts
        # them directly.
        env_vars.append(
            {"name": str(param.key).upper(), "value": cast(str, param.value)}
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
        runtime={
            "container_groups": [
                {
                    "replica_count": int(os.getenv("MCP_WORKLOAD_REPLICA_COUNT", "1")),
                    "containers": [
                        {
                            "name": WORKLOAD_CONTAINER_NAME,
                            "resource_allocation": {
                                "cpu": float(os.getenv("MCP_WORKLOAD_CPU", "1")),
                                "memory": int(
                                    os.getenv(
                                        "MCP_WORKLOAD_MEMORY",
                                        str(DEFAULT_WORKLOAD_MEMORY_BYTES),
                                    )
                                ),
                            },
                        }
                    ],
                }
            ]
        },
        opts=pulumi.ResourceOptions(
            depends_on=depends_on,
            delete_before_replace=False,
            retain_on_delete=False,
        ),
    )


def _export_workload_endpoints(
    mcp_server_asset_name: str, workload: pulumi_datarobot.Workload
) -> pulumi.Output[str]:
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
    return mcp_workload_endpoint


def _create_workload_image_artifact(
    *,
    mcp_server_asset_name: str,
    workload_api_endpoint: str,
    catalog: FilesCatalogBundle,
    bundle_hash: str,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]] | None,
    build_timeout_s: int,
    dockerfile_relative_path: str | None,
    execution_environment: pulumi_datarobot.ExecutionEnvironment | None,
) -> WorkloadImageArtifact | WorkloadGeneratedImageArtifact:
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
            routes=routes,
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
        routes=routes,
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
    mcp_workload_endpoint = _export_workload_endpoints(mcp_server_asset_name, workload)

    return {
        "execution_environment": execution_environment,
        "deployment": None,
        "mcp_server_mcp_endpoint": mcp_workload_endpoint,
        "mcp_server_base_endpoint": workload.endpoint,
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

    workload_artifact_spec = build_artifact_from_image_uri(
        artifact_name=mcp_server_asset_name,
        container_name=WORKLOAD_CONTAINER_NAME,
        container_port=_resolve_container_port(),
        image_uri=workload_image_uri,
        environment_vars=_workload_environment_vars(mcp_server_asset_name),
        # Only override the image's own entrypoint when explicitly configured.
        entrypoints=_explicit_workload_entrypoint(),
        routes=get_workload_mcp_oauth_routes(),
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
    mcp_workload_endpoint = _export_workload_endpoints(mcp_server_asset_name, workload)

    return {
        "execution_environment": None,
        "deployment": None,
        "mcp_server_mcp_endpoint": mcp_workload_endpoint,
        "mcp_server_base_endpoint": workload.endpoint,
        "mcp_custom_model_runtime_parameters": [],
    }
