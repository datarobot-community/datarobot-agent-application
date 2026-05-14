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
from pathlib import Path
import re
import shutil
from typing import cast, Final, Optional, Any, Sequence
import yaml  # type: ignore[import-untyped]

import datarobot as dr
import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi import export, resolve_execution_environment_version
from datarobot_pulumi_utils.pulumi.custom_model_deployment import CustomModelDeployment
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME
from datarobot_pulumi_utils.schema.custom_models import (
    DeploymentArgs,
    RegisteredModelArgs,
)
from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments


from . import project_dir, use_case

from .llm import custom_model_runtime_parameters as llm_custom_model_runtime_parameters

DEFAULT_EXECUTION_ENVIRONMENT = "Python 3.11 GenAI Agents"

# Toggle for High Availability (HA) and Load Balancing configuration for agent deployment
# To enable HA mode: Add ENABLE_AGENT_HA_MODE="true" to your .env file in the project root
# When enabled: workers=5, resource_bundle=cpu.5xlarge, replicas=2, max_computes=4
# When disabled (default): workers=2, resource_bundle=cpu.3xlarge, replicas=1, max_computes=2
ENABLE_AGENT_HA_MODE = os.environ.get("ENABLE_AGENT_HA_MODE", "false").lower() == "true"

# Custom Model DRUM runtime parameters (concurrency configuration)
DEFAULT_CUSTOM_MODEL_WORKERS: Final[str] = "5" if ENABLE_AGENT_HA_MODE else "2"
DEFAULT_DRUM_SERVER_TYPE: Final[str] = "gunicorn"
DEFAULT_DRUM_GUNICORN_WORKER_CLASS: Final[str] = "sync"
DEFAULT_DRUM_WORKER_CONNECTIONS: Final[str] = "1"
# Default gunicorn timeout in current DRUM is 2 mins
DEFAULT_DRUM_CLIENT_REQUEST_TIMEOUT: Final[str] = "300"

# DRUM runtime parameters that are safe to include defaultValue in metadata
DRUM_PARAMS_WITH_DEFAULTS: Final[set[str]] = {
    "CUSTOM_MODEL_WORKERS",
    "DRUM_SERVER_TYPE",
    "DRUM_GUNICORN_WORKER_CLASS",
    "DRUM_WORKER_CONNECTIONS",
    "DRUM_CLIENT_REQUEST_TIMEOUT",
}

# Custom Model resource bundle configuration
DEFAULT_AGENT_RESOURCE_BUNDLE_ID: Final[str] = (
    "cpu.5xlarge" if ENABLE_AGENT_HA_MODE else "cpu.3xlarge"
)
DEFAULT_AGENT_REPLICAS: Final[int] = 2 if ENABLE_AGENT_HA_MODE else 1

# Agent deployment configuration (HPA autoscaling)
DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES: Final[int] = 0
DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES: Final[int] = 4 if ENABLE_AGENT_HA_MODE else 2


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
    ]
]


__all__ = [
    "agent_application_name",
    "agent_application_path",
    "agent_prediction_environment",
    "agent_custom_model",
    "agent_agent_deployment_id",
    "agent_registered_model_args",
    "agent_deployment_args",
    "agent_agent_deployment",
    "agent_app_runtime_parameters",
    "agent_agent_runtime_parameters",
]

agent_application_name: str = "agent"
agent_asset_name: str = f"[{PROJECT_NAME}] [agent]"
agent_application_path = project_dir.parent / "agent"

_is_dragent_server_enabled = (
    os.environ.get("ENABLE_DRAGENT_SERVER", "").strip().lower() == "true"
)


def _check_a2a_server_enabled() -> bool:
    workflow_yaml_path = project_dir.parent / "agent" / "agent" / "workflow.yaml"
    if not workflow_yaml_path.exists():
        return False
    with open(workflow_yaml_path) as f:
        workflow_config = yaml.safe_load(f) or {}
    a2a = ((workflow_config.get("general") or {}).get("front_end") or {}).get("a2a")
    return a2a is not None


_is_a2a_server_enabled = _check_a2a_server_enabled()


def _check_okta_xaa_credentials_needed() -> bool:
    """Check if Okta XAA client credentials (PRINCIPAL_ID, PRIVATE_JWK) are needed.

    These are required when the agent uses the okta_cross_app_access auth provider
    to call remote XAA-protected agents. Server-side cross_application_access config
    only advertises XAA requirements on the agent card and does not need these credentials.
    """
    workflow_yaml_path = project_dir.parent / "agent" / "agent" / "workflow.yaml"
    if not workflow_yaml_path.exists():
        return False
    with open(workflow_yaml_path) as f:
        workflow_config = yaml.safe_load(f) or {}
    auth_section = workflow_config.get("authentication") or {}
    return any(
        isinstance(cfg, dict) and cfg.get("_type") == "okta_cross_app_access"
        for cfg in auth_section.values()
    )


_is_okta_xaa_credentials_needed = _check_okta_xaa_credentials_needed()


def _generate_metadata_yaml(
    agent_name: str,
    custom_model_folder: str,
    runtime_parameter_values: Sequence[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> None:
    """Generate model-metadata.yaml file from scratch with runtime parameters.

    Args:
        agent_name: Name of the agent
        custom_model_folder: Path to the custom model folder
        runtime_parameter_values: List of runtime parameter definitions

    Raises:
        OSError: If unable to write the metadata file
    """
    # Build runtime parameter definitions, excluding Pulumi Output objects
    runtime_param_defs = []
    for param in runtime_parameter_values:
        param_def = {
            "fieldName": param.key,
            "type": param.type,
        }
        # Only include defaultValue for safe parameters (allowlisted DRUM params)
        if (
            hasattr(param, "value")
            and param.value
            and not isinstance(param.value, pulumi.Output)
            and param.key in DRUM_PARAMS_WITH_DEFAULTS
        ):
            param_def["defaultValue"] = param.value
        runtime_param_defs.append(param_def)

    metadata = {
        "name": agent_name,
        "type": "inference",
        "targetType": "agenticworkflow",
        "runtimeParameterDefinitions": runtime_param_defs,
    }

    # Write the file using yaml library for proper formatting
    metadata_output_path = Path(custom_model_folder) / "model-metadata.yaml"
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.write_text(
        yaml.dump(
            metadata, default_flow_style=False, sort_keys=False, explicit_start=True
        ),
        encoding="utf-8",
    )


def get_custom_model_files(
    custom_model_folder: str,
    runtime_parameter_values: Sequence[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> list[tuple[str, str]]:
    # generate model-metadata.yaml file in the custom model folder
    _generate_metadata_yaml(
        agent_name="agent",
        custom_model_folder=custom_model_folder,
        runtime_parameter_values=runtime_parameter_values,
    )
    # Get all files from application path, following symlinks
    # When we've upgraded to Python 3.13 we can use Path.glob(reduce_symlinks=True)
    # https://docs.python.org/3.13/library/pathlib.html#pathlib.Path.glob
    source_files = []
    for dirpath, dirnames, filenames in os.walk(custom_model_folder, followlinks=True):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(file_path, custom_model_folder)
            # Convert to forward slashes for Linux destination
            rel_path = rel_path.replace(os.path.sep, "/")
            source_files.append((os.path.abspath(file_path), rel_path))
    source_files = [
        (file_path, file_name)
        for file_path, file_name in source_files
        if not any(
            exclude_pattern.match(file_name) for exclude_pattern in EXCLUDE_PATTERNS
        )
    ]
    return source_files


def synchronize_pyproject_dependencies():
    pyproject_toml_path = os.path.join(str(agent_application_path), "pyproject.toml")
    uv_lock_path = os.path.join(str(agent_application_path), "uv.lock")
    docker_context_folder = str(
        os.path.join(str(agent_application_path), "docker_context")
    )

    # Check if pyproject.toml exists in the application path
    if not os.path.exists(pyproject_toml_path):
        return

    # Copy pyproject.toml to docker_context folder if it exists
    if os.path.exists(docker_context_folder):
        docker_context_pyproject_path = os.path.join(
            docker_context_folder, "pyproject.toml"
        )
        shutil.copy2(pyproject_toml_path, docker_context_pyproject_path)
        if os.path.exists(uv_lock_path):
            docker_context_uv_lock_path = os.path.join(docker_context_folder, "uv.lock")
            shutil.copy2(uv_lock_path, docker_context_uv_lock_path)


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
        import importlib

        # Ensure relative import format
        module_path = module if module.startswith(".") else f".{module}"
        imported_module = importlib.import_module(module_path, package=__package__)
        return getattr(imported_module, object_name, None)
    except (ImportError, AttributeError):
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
    Load MCP runtime parameters from the MCP Deployment module if available,
    otherwise fall back to environment variables.
    """
    mcp_module = "mcp_server"

    mcp_params = maybe_import_from_module(
        mcp_module, "mcp_custom_model_runtime_parameters"
    )
    if mcp_params is not None:
        return mcp_params

    return get_mcp_runtime_parameters_from_env()


def _update_deployment_predictions_settings(
    deployment_id: str,
    min_computes: int,
    max_computes: int,
) -> str:
    """Update deployment predictions settings for autoscaling configuration.

    NOTES:
    - predictions_settings is ignored during deployment creation
    due to DataRobot server-side hardcoded default value
    - min_computes must be either 0 or equal to max_computes
    for custom model deployments
    """
    if min_computes not in (0, max_computes):
        error_msg = (
            f"Invalid deployment configuration: DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES={min_computes}\n"
            f"min_computes must be either 0 or equal to max_computes ({max_computes}).\n"
            f"Update DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES to either 0 or {max_computes}."
        )
        pulumi.log.error(error_msg)
        raise ValueError(error_msg)
    dr_client = dr.Client()

    # GET current settings to preserve server-side defaults
    response = dr_client.get(f"deployments/{deployment_id}/settings/")
    current_settings = response.json()
    current_predictions_settings = current_settings.get("predictionsSettings", {})

    # Merge overrides into the existing predictions settings
    current_predictions_settings["minComputes"] = min_computes
    current_predictions_settings["maxComputes"] = max_computes

    # PATCH with the merged settings
    dr_client.patch(
        f"deployments/{deployment_id}/settings/",
        json={"predictionsSettings": current_predictions_settings},
    )
    pulumi.info(
        f"Updated deployment {deployment_id} predictions settings: "
        f"min_computes={min_computes}, max_computes={max_computes}"
    )
    return deployment_id


synchronize_pyproject_dependencies()
pulumi.info("NOTE: [unknown] values will be populated after performing an update.")  # fmt: skip

if ENABLE_AGENT_HA_MODE:
    pulumi.info(
        f"High Availability mode enabled, agent deployment will be configured with:\n"
        f"- workers: {DEFAULT_CUSTOM_MODEL_WORKERS}\n"
        f"- resource_bundle: {DEFAULT_AGENT_RESOURCE_BUNDLE_ID}\n"
        f"- replicas: {DEFAULT_AGENT_REPLICAS}\n"
        f"- max_computes: {DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES}"
    )

# Start of Pulumi settings and application infrastructure
_dr_exec_env = os.environ.get("DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT", "").strip()
if len(_dr_exec_env) > 0:
    # Get the default execution environment from environment variable
    execution_environment_id = _dr_exec_env
    if DEFAULT_EXECUTION_ENVIRONMENT in execution_environment_id:
        pulumi.info("Using default GenAI Agentic Execution Environment.")
        execution_environment_id = RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.id

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

    agent_execution_environment = pulumi_datarobot.ExecutionEnvironment.get(
        id=execution_environment_id,
        version_id=execution_environment_version_id,
        resource_name=agent_asset_name + " Execution Environment",
    )
else:
    agent_exec_env_use_cases = ["customModel", "notebook"]
    if os.path.exists(
        os.path.join(str(agent_application_path), "docker_context.tar.gz")
    ):
        pulumi.info(
            "Using prebuilt Dockerfile docker_context.tar.gz to run the execution environment"
        )
        agent_execution_environment = pulumi_datarobot.ExecutionEnvironment(
            resource_name=agent_asset_name + " Execution Environment",
            name=agent_asset_name + " Execution Environment",
            description="Execution Environment for " + agent_asset_name,
            programming_language="python",
            docker_image=os.path.join(
                str(agent_application_path), "docker_context.tar.gz"
            ),
            use_cases=agent_exec_env_use_cases,
        )
    else:
        pulumi.info("Using docker_context folder to compile the execution environment")
        agent_execution_environment = pulumi_datarobot.ExecutionEnvironment(
            resource_name=agent_asset_name + " Execution Environment",
            name=agent_asset_name + " Execution Environment",
            description="Execution Environment for " + agent_asset_name,
            programming_language="python",
            docker_context_path=os.path.join(
                str(agent_application_path), "docker_context"
            ),
            use_cases=agent_exec_env_use_cases,
        )

# Prepare runtime parameters for agent custom model deployment
agent_runtime_parameter_values: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = [] + llm_custom_model_runtime_parameters + get_mcp_custom_model_runtime_parameters()

# DRUM runtime parameters for concurrency configuration
agent_runtime_parameter_values.extend(
    [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="CUSTOM_MODEL_WORKERS",
            type="numeric",
            value=DEFAULT_CUSTOM_MODEL_WORKERS,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="DRUM_SERVER_TYPE",
            type="string",
            value=DEFAULT_DRUM_SERVER_TYPE,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="DRUM_GUNICORN_WORKER_CLASS",
            type="string",
            value=DEFAULT_DRUM_GUNICORN_WORKER_CLASS,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="DRUM_WORKER_CONNECTIONS",
            type="numeric",
            value=DEFAULT_DRUM_WORKER_CONNECTIONS,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="DRUM_CLIENT_REQUEST_TIMEOUT",
            type="numeric",
            value=DEFAULT_DRUM_CLIENT_REQUEST_TIMEOUT,
        ),
    ]
)


# Handle session secret key credential
SESSION_SECRET_KEY: Final[str] = "SESSION_SECRET_KEY"

if session_secret_key := os.environ.get(SESSION_SECRET_KEY):
    pulumi.export(SESSION_SECRET_KEY, session_secret_key)
    session_secret_cred = pulumi_datarobot.ApiTokenCredential(
        agent_asset_name + " Session Secret Key",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=str(session_secret_key)),
    )
    agent_runtime_parameter_values.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            type="credential",
            key=SESSION_SECRET_KEY,
            value=session_secret_cred.id,
        ),
    )

# Handle Okta XAA credentials for A2A authentication
if _is_okta_xaa_credentials_needed:
    PRINCIPAL_ID_KEY: Final[str] = "PRINCIPAL_ID"
    principal_id = os.environ.get(PRINCIPAL_ID_KEY, "")
    if principal_id:
        agent_runtime_parameter_values.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=PRINCIPAL_ID_KEY,
                type="string",
                value=principal_id,
            ),
        )
        pulumi.info(f"XAA configured with PRINCIPAL_ID: {principal_id}")

    PRIVATE_JWK_KEY: Final[str] = "PRIVATE_JWK"
    private_jwk = os.environ.get(PRIVATE_JWK_KEY)
    if private_jwk:
        private_jwk_cred = pulumi_datarobot.ApiTokenCredential(
            agent_asset_name + " Private JWK",
            args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=str(private_jwk)),
        )
        agent_runtime_parameter_values.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                type="credential",
                key=PRIVATE_JWK_KEY,
                value=private_jwk_cred.id,
            ),
        )
        pulumi.info("XAA configured with PRIVATE_JWK credential")

if _is_dragent_server_enabled:
    enable_dragent_server_runtime_param = (
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="ENABLE_DRAGENT_SERVER",
            type="boolean",
            value="true",
        )
    )
    agent_runtime_parameter_values.append(enable_dragent_server_runtime_param)

agent_custom_model_files = get_custom_model_files(
    custom_model_folder=str(agent_application_path),
    runtime_parameter_values=agent_runtime_parameter_values,
)

agent_custom_model = pulumi_datarobot.CustomModel(
    resource_name=agent_asset_name + " Custom Model",
    name=agent_asset_name + " Custom Model",
    base_environment_id=agent_execution_environment.id,
    base_environment_version_id=agent_execution_environment.version_id,
    target_type="AgenticWorkflow",
    target_name="response",
    resource_bundle_id=DEFAULT_AGENT_RESOURCE_BUNDLE_ID,
    replicas=DEFAULT_AGENT_REPLICAS,
    language="python",
    use_case_ids=[use_case.id],
    files=agent_custom_model_files,
    runtime_parameter_values=agent_runtime_parameter_values,
)

agent_custom_model_endpoint = agent_custom_model.id.apply(
    lambda id: (
        f"{os.getenv('DATAROBOT_ENDPOINT')}/genai/agents/fromCustomModel/{id}/chat/"
    )
)

agent_playground = pulumi_datarobot.Playground(
    name=agent_asset_name + " Agentic Playground",
    resource_name=agent_asset_name + " Agentic Playground",
    description="Experimentation Playground for " + agent_asset_name,
    use_case_id=use_case.id,
    playground_type="agentic",
)

agent_blueprint = pulumi_datarobot.LlmBlueprint(
    name=agent_asset_name + " LLM Blueprint",
    resource_name=agent_asset_name + " LLM Blueprint",
    playground_id=agent_playground.id,
    llm_id="chat-interface-custom-model",
    llm_settings=pulumi_datarobot.LlmBlueprintLlmSettingsArgs(
        custom_model_id=agent_custom_model.id
    ),
    prompt_type="ONE_TIME_PROMPT",
)

datarobot_url = (
    os.getenv("DATAROBOT_ENDPOINT", "https://app.datarobot.com/api/v2")
    .rstrip("/")
    .rstrip("/api/v2")
)

agent_playground_url = pulumi.Output.format(
    "{0}/usecases/{1}/agentic-playgrounds/{2}/comparison/chats",
    datarobot_url,
    use_case.id,
    agent_playground.id,
)


# Export the IDs of the created resources
pulumi.export(
    "Agent Execution Environment ID " + agent_asset_name,
    agent_execution_environment.id,
)
pulumi.export(
    "Agent Custom Model Chat Endpoint " + agent_asset_name,
    agent_custom_model_endpoint,
)
pulumi.export("Agent Playground URL " + agent_asset_name, agent_playground_url)  # fmt: skip


agent_agent_deployment_id: pulumi.Output[str] = cast(pulumi.Output[str], "None")
agent_deployment_endpoint: pulumi.Output[str] = cast(pulumi.Output[str], "None")
agent_deployment_a2a_endpoint: pulumi.Output[str] = cast(pulumi.Output[str], "None")
if os.environ.get("AGENT_DEPLOY") != "0":
    if prediction_environment_id := os.environ.get(
        "DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT"
    ):
        pulumi.info(
            f"Using existing prediction environment '{prediction_environment_id}'"
        )

        agent_prediction_environment = pulumi_datarobot.PredictionEnvironment.get(
            id=prediction_environment_id,
            resource_name=agent_asset_name + " Prediction Environment [PRE-EXISTING]",
        )
    else:
        agent_prediction_environment = pulumi_datarobot.PredictionEnvironment(
            resource_name=agent_asset_name + " Prediction Environment",
            name=agent_asset_name + " Prediction Environment",
            platform=dr.enums.PredictionEnvironmentPlatform.DATAROBOT_SERVERLESS,
            opts=pulumi.ResourceOptions(retain_on_delete=False),
        )

    agent_registered_model_args = RegisteredModelArgs(
        resource_name=agent_asset_name + " Registered Model",
        name=agent_asset_name + " Registered Model",
    )

    agent_deployment_args = DeploymentArgs(
        resource_name=agent_asset_name + " Deployment",
        label=agent_asset_name + " Deployment",
        association_id_settings=pulumi_datarobot.DeploymentAssociationIdSettingsArgs(
            column_names=["association_id"],
            auto_generate_id=False,
            required_in_prediction_requests=True,
        ),
        predictions_data_collection_settings=(
            pulumi_datarobot.DeploymentPredictionsDataCollectionSettingsArgs(
                enabled=True
            )
        ),
    )

    agent_agent_deployment = CustomModelDeployment(
        resource_name=agent_asset_name + " Chat Deployment",
        use_case_ids=[use_case.id],
        custom_model_version_id=agent_custom_model.version_id,
        prediction_environment=agent_prediction_environment,
        registered_model_args=agent_registered_model_args,
        deployment_args=agent_deployment_args,
    )

    # Update autoscaling predictions_settings for agent deployment
    agent_agent_deployment.id.apply(
        lambda dep_id: _update_deployment_predictions_settings(
            deployment_id=dep_id,
            min_computes=DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES,
            max_computes=DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES,
        )
    )

    agent_agent_deployment_id = agent_agent_deployment.id.apply(lambda id: f"{id}")
    agent_deployment_endpoint = agent_agent_deployment.id.apply(
        lambda id: (
            f"{os.getenv('DATAROBOT_ENDPOINT')}/deployments/{id}/directAccess"
            if _is_dragent_server_enabled
            else f"{os.getenv('DATAROBOT_ENDPOINT')}/deployments/{id}"
        )
    )
    agent_deployment_completions_endpoint = agent_agent_deployment.id.apply(
        lambda id: (
            f"{os.getenv('DATAROBOT_ENDPOINT')}/deployments/{id}/chat/completions"
        )
    )
    agent_deployment_a2a_endpoint = agent_agent_deployment.id.apply(
        lambda id: (
            f"{os.getenv('DATAROBOT_ENDPOINT')}/deployments/{id}/directAccess/a2a/"
        )
    )

    export(
        agent_application_name.upper() + "_DEPLOYMENT_ID",
        agent_agent_deployment.id,
    )
    pulumi.export(
        "Agent Deployment Chat Endpoint " + agent_asset_name,
        agent_deployment_completions_endpoint,
    )

agent_app_runtime_parameters = [
    pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
        key=agent_application_name.upper() + "_DEPLOYMENT_ID",
        type="string",
        value=agent_agent_deployment_id,
    ),
    pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
        key=agent_application_name.upper() + "_ENDPOINT",
        type="string",
        value=agent_deployment_endpoint,
    ),
]
if _is_dragent_server_enabled:
    agent_app_runtime_parameters.append(
        pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
            key="ENABLE_DRAGENT_SERVER",
            type="boolean",
            value="true",
        ),
    )

agent_agent_runtime_parameters = [
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key=agent_application_name.upper() + "_DEPLOYMENT_ID",
        type="string",
        value=agent_agent_deployment_id,
    ),
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
        key=agent_application_name.upper() + "_ENDPOINT",
        type="string",
        value=agent_deployment_endpoint,
    ),
]
if _is_dragent_server_enabled and _is_a2a_server_enabled:
    agent_agent_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=agent_application_name.upper() + "_A2A_ENDPOINT",
            type="string",
            value=agent_deployment_a2a_endpoint,
        ),
    )
