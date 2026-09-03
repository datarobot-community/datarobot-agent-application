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

"""Shared config assembly for both agent runtimes (Custom Models and Workload API).

Owns everything that is identical regardless of ``ENABLE_AGENT_ON_WORKLOAD_API``:
execution-environment resolution, LLM/MCP/memory/session/IDP runtime-parameter
assembly, memory-space provisioning, and A2A detection. The only Pulumi
resources created here are credentials and (when memory is
``datarobot_memory_service``) the ``MemorySpace`` — both runtime-agnostic.
Runtime-specific resources (``CustomModel``/``Playground``/``LlmBlueprint`` for
Custom Models; ``Artifact``/``Workload`` for Workload API) live in
``deployment.py``/``workload.py`` respectively, which never check the runtime
flag themselves and never import each other.
"""

from __future__ import annotations

import importlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Final, Optional

import pulumi
import pulumi_datarobot
import yaml  # type: ignore[import-untyped]
from datarobot_pulumi_utils.pulumi import export, resolve_execution_environment_version
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME
from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments

from .. import project_dir
from ..llm import custom_model_runtime_parameters as llm_custom_model_runtime_parameters

logger = logging.getLogger(__name__)

DEFAULT_EXECUTION_ENVIRONMENT = "Python 3.11 GenAI Agents"

agent_application_name: str = "agent"
agent_asset_name: str = f"[{PROJECT_NAME}] [agent]"
agent_application_path = project_dir.parent / "agent"

# Toggle for High Availability (HA) and Load Balancing configuration for agent deployment.
# To enable HA mode: Add ENABLE_AGENT_HA_MODE="true" to your .env file in the project root.
# This only sizes the Custom Models resource bundle/replicas (see deployment.py) — Workload
# API sizing is fully independent via WORKLOAD_CPU/WORKLOAD_MEMORY/WORKLOAD_REPLICA_COUNT.
ENABLE_AGENT_HA_MODE = os.environ.get("ENABLE_AGENT_HA_MODE", "false").lower() == "true"

# Gunicorn worker timeout (seconds) for the dragent front end, read by datarobot-genai
# whenever the process is started with `--use_gunicorn true`. Shared across runtimes: the
# Custom Models container always uses it, and so does the Workload API generated-Dockerfile
# scenario's run_server.sh (see workload.py). Raised above gunicorn's 30s default so long
# agent turns aren't killed mid-stream.
DEFAULT_AGENT_GUNICORN_WORKER_TIMEOUT: Final[str] = "600"

AGENT_CARD_REGISTRY_MEMORY_SPACE_ID: Final[str] = "AGENT_CARD_REGISTRY_MEMORY_SPACE_ID"

SESSION_SECRET_KEY: Final[str] = "SESSION_SECRET_KEY"
IDP_AGENT_ID_PARAM: Final[str] = "IDP_AGENT_ID"
PRIVATE_JWK_PARAM: Final[str] = "IDP_AGENT_PRIVATE_KEY_JWK"

EXCLUDE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r".*tests/.*",
        r".*\.coverage",
        r".*\.DS_Store",
        r".*\.pyc",
        r".*\.ruff_cache/.*",
        r".*\.venv/.*",
        r".*\.mypy_cache/.*",
        r".*__pycache__/.*",
        r".*\.pytest_cache/.*",
        r".*\.uv/.*",
        r".*docker_context/.*",
        r".*\.env(?:\.[A-Za-z0-9_-]+)*$",
    ]
]

# Co-deployed MCP is auto-wired by this name; renamed/extra MCP → env vars.
MCP_MODULE_NAME: Final[str] = "mcp_server"

# The co-deployed MCP module (if any) lives at infra/mcp_server.py, a sibling
# of the infra.agent_infra package this module lives in -- not inside it.
# Resolve one level up from __package__ (rather than hardcoding "infra") so this
# still works if the top-level package is ever renamed.
_TOP_LEVEL_INFRA_PACKAGE: Final[str] = (__package__ or "").rsplit(".", 1)[0]


def _find_workflow_yaml() -> Path | None:
    """Locate workflow.yaml for the agent.

    Checks the agent root directory first, then falls back to the agent/ subdirectory.
    """
    base = project_dir.parent / "agent"

    primary = base / "workflow.yaml"
    if primary.exists():
        return primary

    fallback = base / "agent" / "workflow.yaml"
    if fallback.exists():
        return fallback

    return None


def _is_truthy_yaml_value(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "enabled")
    return bool(value)


def _load_workflow_config() -> dict[str, Any]:
    workflow_yaml_path = _find_workflow_yaml()
    if workflow_yaml_path is None:
        return {}
    with open(workflow_yaml_path) as f:
        return yaml.safe_load(f) or {}


def check_a2a_server_enabled() -> bool:
    workflow_config = _load_workflow_config()
    a2a = ((workflow_config.get("general") or {}).get("front_end") or {}).get("a2a")
    return a2a is not None


def _check_a2a_remote_client_enabled() -> bool:
    """Return whether workflow.yaml declares remote A2A agent clients."""
    function_groups = _load_workflow_config().get("function_groups") or {}
    for fg_config in function_groups.values():
        if (
            isinstance(fg_config, dict)
            and fg_config.get("_type") == "authenticated_a2a_client"
        ):
            return True
    return False


def check_a2a_unauthenticated_well_known_route_enabled() -> bool:
    workflow_yaml_path = _find_workflow_yaml()
    if workflow_yaml_path is None:
        return False
    with open(workflow_yaml_path) as f:
        workflow_config = yaml.safe_load(f) or {}
    a2a = ((workflow_config.get("general") or {}).get("front_end") or {}).get("a2a")
    if not isinstance(a2a, dict):
        return False
    return _is_truthy_yaml_value(a2a.get("enable_unauthenticated_well_known_route"))


IS_A2A_SERVER_ENABLED = check_a2a_server_enabled()
IS_A2A_REMOTE_CLIENT_ENABLED = _check_a2a_remote_client_enabled()
IS_A2A_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENABLED = (
    check_a2a_unauthenticated_well_known_route_enabled()
)


def resolve_agent_execution_environment(
    *,
    asset_name: str,
    application_path: Path,
    use_cases: list[str],
) -> pulumi_datarobot.ExecutionEnvironment:
    """Resolve (or build) the agent's execution environment.

    Controlled by ``DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT``:

    - **unset** (default): build a new ``ExecutionEnvironment`` from
      ``docker_context.tar.gz`` when present under ``application_path``, otherwise
      from the ``docker_context`` folder.
    - **set to the GenAI default name** (containing
      ``"Python 3.11 GenAI Agents"``): normalized to
      ``RuntimeEnvironments.PYTHON_311_GENAI_AGENTS`` and referenced via
      ``ExecutionEnvironment.get`` (optionally pinned with
      ``DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID``).
    - **set to any other value**: treated as a pre-existing execution environment
      ID and referenced via ``ExecutionEnvironment.get`` (same version pinning).

    ``use_cases`` controls the ``ExecutionEnvironment.use_cases`` argument used
    only in the "build a new one" branch. Custom Models passes
    ``["customModel", "notebook"]`` — the ``"notebook"`` tag is load-bearing for
    Playground's ephemeral-codespace fallback (see deployment.py). Workload
    API's generated-Dockerfile scenario passes only ``["customModel"]``, since it
    has no Playground/codespace use.
    """
    dr_exec_env = os.environ.get("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", "").strip()
    if len(dr_exec_env) > 0:
        execution_environment_id = dr_exec_env
        if DEFAULT_EXECUTION_ENVIRONMENT in execution_environment_id:
            pulumi.info("Using default GenAI Agentic Execution Environment.")
            execution_environment_id = (
                RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.id
            )

        execution_environment_version_id = resolve_execution_environment_version(
            execution_environment_id,
            "DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT_VERSION_ID",
        )

        pulumi.info(
            "Using existing execution environment: "
            + execution_environment_id
            + " Version ID: "
            + str(execution_environment_version_id)
        )

        return pulumi_datarobot.ExecutionEnvironment.get(
            id=execution_environment_id,
            version_id=execution_environment_version_id,
            resource_name=asset_name + " Execution Environment",
        )

    if os.path.exists(os.path.join(str(application_path), "docker_context.tar.gz")):
        pulumi.info(
            "Using prebuilt Dockerfile docker_context.tar.gz to run the execution environment"
        )
        return pulumi_datarobot.ExecutionEnvironment(
            resource_name=asset_name + " Execution Environment",
            name=asset_name + " Execution Environment",
            description="Execution Environment for " + asset_name,
            programming_language="python",
            docker_image=os.path.join(str(application_path), "docker_context.tar.gz"),
            use_cases=use_cases,
        )

    pulumi.info("Using docker_context folder to compile the execution environment")
    return pulumi_datarobot.ExecutionEnvironment(
        resource_name=asset_name + " Execution Environment",
        name=asset_name + " Execution Environment",
        description="Execution Environment for " + asset_name,
        programming_language="python",
        docker_context_path=os.path.join(str(application_path), "docker_context"),
        use_cases=use_cases,
    )


def maybe_import_from_module(module: str, object_name: str) -> Optional[Any]:
    """Attempt to import an object from a module.

    Args:
        module: The module name to import from (can include relative imports like ".module_name")
        object_name: The name of the object to import from the module

    Returns:
        The imported object if successful, None otherwise
    """
    if not module:
        return None

    try:
        # Ensure relative import format
        module_path = module if module.startswith(".") else f".{module}"
        imported_module = importlib.import_module(
            module_path, package=_TOP_LEVEL_INFRA_PACKAGE
        )
        return getattr(imported_module, object_name, None)
    except (ImportError, AttributeError) as exc:
        logger.debug("Skipping module '%s' due to import error: %s", module, exc)
        return None


def get_mcp_runtime_parameters_from_env() -> list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
]:
    mcp_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ] = []

    # Add MCP runtime parameters if configured
    if os.environ.get("MCP_DEPLOYMENT_ID"):
        mcp_deployment_id = os.environ["MCP_DEPLOYMENT_ID"]
        mcp_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="MCP_DEPLOYMENT_ID",
                type="string",
                value=mcp_deployment_id,
            )
        )
        pulumi.info(f"MCP configured with DataRobot MCP Server: {mcp_deployment_id}")

    # Allow external mcp server. Currently, code will use MCP_DEPLOYMENT_ID first and if that is empty
    # then use the EXTERNAL_MCP_URL
    if os.environ.get("EXTERNAL_MCP_URL"):
        external_mcp_url = os.environ["EXTERNAL_MCP_URL"].rstrip("/")
        mcp_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="EXTERNAL_MCP_URL",
                type="string",
                value=external_mcp_url,
            )
        )
        pulumi.info(f"MCP configured with external server: {external_mcp_url}")

    # Add optional EXTERNAL_MCP_HEADERS
    external_mcp_headers = os.environ.get("EXTERNAL_MCP_HEADERS")
    if external_mcp_headers:
        mcp_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="EXTERNAL_MCP_HEADERS",
                type="string",
                value=external_mcp_headers,
            )
        )
        pulumi.info(f"External MCP configured with headers: {external_mcp_headers}")

    # Add optional EXTERNAL_MCP_TRANSPORT parameter
    external_mcp_transport = os.environ.get("EXTERNAL_MCP_TRANSPORT")
    if external_mcp_transport:
        external_mcp_transport = os.environ["EXTERNAL_MCP_TRANSPORT"]
        mcp_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="EXTERNAL_MCP_TRANSPORT",
                type="string",
                value=external_mcp_transport,
            )
        )
        pulumi.info(f"External MCP configured with transport: {external_mcp_transport}")

    return mcp_runtime_parameters


def get_mcp_custom_model_runtime_parameters() -> list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
]:
    """
    Load MCP runtime parameters from the conventionally-named MCP module when it
    is present in the project, otherwise fall back to environment variables.
    """
    mcp_params = maybe_import_from_module(
        MCP_MODULE_NAME, "mcp_custom_model_runtime_parameters"
    )
    if mcp_params is not None:
        return mcp_params
    return get_mcp_runtime_parameters_from_env()


def build_shared_agent_runtime_parameters() -> list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
]:
    """Assemble the LLM/MCP/memory/session/IDP runtime parameters shared by both runtimes.

    Meant to be called exactly once by the entry router, regardless of which
    runtime ends up consuming the result: Custom Models passes the list
    straight into ``CustomModel.runtime_parameter_values`` (after appending its
    own ``CUSTOM_MODEL_WORKERS``); Workload API translates each entry into a
    container env var (plain value, or a ``dr-credential`` reference for
    ``type="credential"`` entries — see ``workload.py``).

    As a side effect, creates the session-secret / IDP-JWK
    credentials — all
    runtime-agnostic. Excludes ``CUSTOM_MODEL_WORKERS``: that parameter is a
    DataRobot custom-model-container gunicorn-wrapper convention with no
    Workload-container equivalent, so it is added only by ``deployment.py``.
    """
    params: list[pulumi_datarobot.CustomModelRuntimeParameterValueArgs] = (
        []
        + llm_custom_model_runtime_parameters
        + get_mcp_custom_model_runtime_parameters()
    )

    params.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="AGENT_GUNICORN_WORKER_TIMEOUT",
            type="string",  # string is type-agnostic; numeric fails str settings fields
            value=DEFAULT_AGENT_GUNICORN_WORKER_TIMEOUT,
        )
    )

    # Handle session secret key credential
    if session_secret_key := os.environ.get(SESSION_SECRET_KEY):
        pulumi.export(SESSION_SECRET_KEY, session_secret_key)
        session_secret_cred = pulumi_datarobot.ApiTokenCredential(
            agent_asset_name + " Session Secret Key",
            args=pulumi_datarobot.ApiTokenCredentialArgs(
                api_token=str(session_secret_key)
            ),
        )
        params.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                type="credential",
                key=SESSION_SECRET_KEY,
                value=session_secret_cred.id,
            ),
        )

    # Agent card registry L2 cache (shared across replicas via DataRobot MemorySpace)
    if IS_A2A_REMOTE_CLIENT_ENABLED:
        agent_registry_cache_memory_space = pulumi_datarobot.MemorySpace(
            agent_asset_name + " Agent Card Registry Cache",
        )
        params.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=AGENT_CARD_REGISTRY_MEMORY_SPACE_ID,
                type="string",
                value=agent_registry_cache_memory_space.id,
            )
        )
        export(
            AGENT_CARD_REGISTRY_MEMORY_SPACE_ID, agent_registry_cache_memory_space.id
        )
        pulumi.export(
            "Agent Card Registry Cache Memory Space ID " + agent_asset_name,
            agent_registry_cache_memory_space.id,
        )

    idp_agent_id = os.environ.get(IDP_AGENT_ID_PARAM, "")
    if idp_agent_id:
        params.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=IDP_AGENT_ID_PARAM,
                type="string",
                value=idp_agent_id,
            ),
        )
        pulumi.info(f"Configured with IDP_AGENT_ID: {idp_agent_id}")

    private_jwk = os.environ.get(PRIVATE_JWK_PARAM)
    if private_jwk:
        private_jwk_cred = pulumi_datarobot.ApiTokenCredential(
            agent_asset_name + " Private JWK",
            args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=str(private_jwk)),
        )
        params.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                type="credential",
                key=PRIVATE_JWK_PARAM,
                value=private_jwk_cred.id,
            ),
        )
        pulumi.info("Configured with IDP_AGENT_PRIVATE_KEY_JWK credential")

    return params
