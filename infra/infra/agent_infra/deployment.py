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

"""Agent provisioning via the Custom Models runtime (today's default).

Creates ``CustomModel`` + ``Playground`` + ``LlmBlueprint`` for agentic
experimentation, and — unless ``AGENT_DEPLOY=0`` — a ``CustomModelDeployment``
for serving. Self-contained: everything specific to this runtime lives here;
shared config comes in via ``base.py``. Never checks
``ENABLE_AGENT_ON_WORKLOAD_API`` itself — the entry router is the only place
that branches on it.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Final, Sequence, cast

import datarobot as dr
import pulumi
import pulumi_datarobot
import yaml  # type: ignore[import-untyped]
from datarobot_pulumi_utils.common import get_datarobot_url
from datarobot_pulumi_utils.pulumi import export
from datarobot_pulumi_utils.pulumi.custom_model_deployment import CustomModelDeployment
from datarobot_pulumi_utils.schema.custom_models import (
    DeploymentArgs,
    RegisteredModelArgs,
)

from .. import use_case
from . import base

# Custom Model resource bundle configuration
DEFAULT_CUSTOM_MODEL_WORKERS: Final[str] = "5" if base.ENABLE_AGENT_HA_MODE else "2"
DEFAULT_AGENT_RESOURCE_BUNDLE_ID: str = (
    "cpu.3xlarge" if base.ENABLE_AGENT_HA_MODE else "cpu.xlarge"
)
DEFAULT_AGENT_REPLICAS: Final[int] = 2 if base.ENABLE_AGENT_HA_MODE else 1
# Agent deployment configuration (HPA autoscaling)
DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES: Final[int] = 0
DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES: Final[int] = (
    4 if base.ENABLE_AGENT_HA_MODE else 2
)

# Runtime parameters that are safe to include defaultValue in metadata
SERVER_PARAMS_WITH_DEFAULTS: Final[set[str]] = {
    "CUSTOM_MODEL_WORKERS",
    "AGENT_GUNICORN_WORKER_TIMEOUT",
}


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
        # Only include defaultValue for safe parameters (allowlisted params)
        if (
            hasattr(param, "value")
            and param.value
            and not isinstance(param.value, pulumi.Output)
            and param.key in SERVER_PARAMS_WITH_DEFAULTS
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
            exclude_pattern.match(file_name)
            for exclude_pattern in base.EXCLUDE_PATTERNS
        )
    ]
    return source_files


def synchronize_pyproject_dependencies() -> None:
    pyproject_toml_path = os.path.join(
        str(base.agent_application_path), "pyproject.toml"
    )
    uv_lock_path = os.path.join(str(base.agent_application_path), "uv.lock")
    docker_context_folder = str(
        os.path.join(str(base.agent_application_path), "docker_context")
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


def provision_deployment_agent(
    shared_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> dict[str, Any]:
    """Provision the agent on the Custom Models runtime.

    ``shared_runtime_parameters`` comes from
    ``base.build_shared_agent_runtime_parameters()``; this function appends the
    one server-tuning parameter that is genuinely Custom-Models-only
    (``CUSTOM_MODEL_WORKERS`` — a DataRobot custom-model-container
    gunicorn-wrapper convention with no Workload-container equivalent), then
    creates the ``CustomModel``, the ``Playground``/``LlmBlueprint`` pair for
    agentic experimentation, and — unless ``AGENT_DEPLOY=0`` — a
    ``CustomModelDeployment`` for serving.
    """
    synchronize_pyproject_dependencies()
    pulumi.info("NOTE: [unknown] values will be populated after performing an update.")  # fmt: skip

    if base.ENABLE_AGENT_HA_MODE:
        pulumi.info(
            f"High Availability mode enabled, agent deployment will be configured with:\n"
            f"- workers: {DEFAULT_CUSTOM_MODEL_WORKERS}\n"
            f"- resource_bundle: {DEFAULT_AGENT_RESOURCE_BUNDLE_ID}\n"
            f"- replicas: {DEFAULT_AGENT_REPLICAS}\n"
            f"- max_computes: {DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES}"
        )

    execution_environment = base.resolve_agent_execution_environment(
        asset_name=base.agent_asset_name,
        application_path=base.agent_application_path,
        use_cases=["customModel", "notebook"],
    )

    agent_runtime_parameter_values = list(shared_runtime_parameters)
    # CUSTOM_MODEL_WORKERS is a custom-model-container gunicorn-wrapper convention
    # with no Workload equivalent, so base.py leaves it out. Insert it immediately
    # before AGENT_GUNICORN_WORKER_TIMEOUT -- the position it held before the infra
    # split -- so upgrading projects see no ordering change in
    # runtime_parameter_values or in the generated model-metadata.yaml, and
    # therefore no spurious custom model version on the next `pulumi up`.
    workers_position = next(
        (
            index
            for index, param in enumerate(agent_runtime_parameter_values)
            if param.key == "AGENT_GUNICORN_WORKER_TIMEOUT"
        ),
        len(agent_runtime_parameter_values),
    )
    agent_runtime_parameter_values.insert(
        workers_position,
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="CUSTOM_MODEL_WORKERS",
            type="numeric",
            value=DEFAULT_CUSTOM_MODEL_WORKERS,
        ),
    )

    custom_model_files = get_custom_model_files(
        custom_model_folder=str(base.agent_application_path),
        runtime_parameter_values=agent_runtime_parameter_values,
    )

    custom_model = pulumi_datarobot.CustomModel(
        resource_name=base.agent_asset_name + " Custom Model",
        name=base.agent_asset_name + " Custom Model",
        base_environment_id=execution_environment.id,
        base_environment_version_id=execution_environment.version_id,
        target_type="AgenticWorkflow",
        target_name="response",
        resource_bundle_id=DEFAULT_AGENT_RESOURCE_BUNDLE_ID,
        replicas=DEFAULT_AGENT_REPLICAS,
        language="python",
        use_case_ids=[use_case.id],
        files=custom_model_files,
        runtime_parameter_values=agent_runtime_parameter_values,
    )

    dr_url = get_datarobot_url()
    dr_web_url = dr_url.removesuffix("/api/v2")

    custom_model_endpoint = custom_model.id.apply(
        lambda id: f"{dr_url}/genai/agents/fromCustomModel/{id}/chat/"
    )

    playground = pulumi_datarobot.Playground(
        name=base.agent_asset_name + " Agentic Playground",
        resource_name=base.agent_asset_name + " Agentic Playground",
        description="Experimentation Playground for " + base.agent_asset_name,
        use_case_id=use_case.id,
        playground_type="agentic",
    )

    pulumi_datarobot.LlmBlueprint(
        name=base.agent_asset_name + " LLM Blueprint",
        resource_name=base.agent_asset_name + " LLM Blueprint",
        playground_id=playground.id,
        llm_id="chat-interface-custom-model",
        llm_settings=pulumi_datarobot.LlmBlueprintLlmSettingsArgs(
            custom_model_id=custom_model.id
        ),
        prompt_type="ONE_TIME_PROMPT",
    )

    playground_url = pulumi.Output.format(
        "{0}/usecases/{1}/agentic-playgrounds/{2}/comparison/chats",
        dr_web_url,
        use_case.id,
        playground.id,
    )

    # Export the IDs of the created resources
    pulumi.export(
        "Agent Execution Environment ID " + base.agent_asset_name,
        execution_environment.id,
    )
    pulumi.export(
        "Agent Custom Model Chat Endpoint " + base.agent_asset_name,
        custom_model_endpoint,
    )
    pulumi.export("Agent Playground URL " + base.agent_asset_name, playground_url)  # fmt: skip

    agent_deployment_id: pulumi.Output[str] = cast(pulumi.Output[str], "None")
    deployment_endpoint: pulumi.Output[str] = cast(pulumi.Output[str], "None")
    deployment_a2a_endpoint: pulumi.Output[str] = cast(pulumi.Output[str], "None")
    agent_deployment = None
    prediction_environment = None
    registered_model_args = None
    deployment_args = None
    if os.environ.get("AGENT_DEPLOY") != "0":
        if prediction_environment_id := os.environ.get(
            "DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT"
        ):
            pulumi.info(
                f"Using existing prediction environment '{prediction_environment_id}'"
            )

            prediction_environment = pulumi_datarobot.PredictionEnvironment.get(
                id=prediction_environment_id,
                resource_name=base.agent_asset_name
                + " Prediction Environment [PRE-EXISTING]",
            )
        else:
            prediction_environment = pulumi_datarobot.PredictionEnvironment(
                resource_name=base.agent_asset_name + " Prediction Environment",
                name=base.agent_asset_name + " Prediction Environment",
                platform=dr.enums.PredictionEnvironmentPlatform.DATAROBOT_SERVERLESS,
                opts=pulumi.ResourceOptions(retain_on_delete=False),
            )

        registered_model_args = RegisteredModelArgs(
            resource_name=base.agent_asset_name + " Registered Model",
            name=base.agent_asset_name + " Registered Model",
        )

        deployment_args = DeploymentArgs(
            resource_name=base.agent_asset_name + " Deployment",
            label=base.agent_asset_name + " Deployment",
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

        agent_deployment = CustomModelDeployment(
            resource_name=base.agent_asset_name + " Chat Deployment",
            use_case_ids=[use_case.id],
            custom_model_version_id=custom_model.version_id,
            prediction_environment=prediction_environment,
            registered_model_args=registered_model_args,
            deployment_args=deployment_args,
        )

        # Update autoscaling predictions_settings for agent deployment
        agent_deployment.id.apply(
            lambda dep_id: _update_deployment_predictions_settings(
                deployment_id=dep_id,
                min_computes=DEFAULT_AGENT_DEPLOYMENT_MIN_COMPUTES,
                max_computes=DEFAULT_AGENT_DEPLOYMENT_MAX_COMPUTES,
            )
        )

        agent_deployment_id = agent_deployment.id.apply(lambda id: f"{id}")
        deployment_endpoint = agent_deployment.id.apply(
            lambda id: f"{dr_url}/deployments/{id}/directAccess"
        )
        deployment_completions_endpoint = agent_deployment.id.apply(
            lambda id: f"{dr_url}/deployments/{id}/chat/completions"
        )
        deployment_a2a_endpoint = agent_deployment.id.apply(
            lambda id: f"{dr_url}/deployments/{id}/directAccess/a2a/"
        )

        export(
            base.agent_application_name.upper() + "_DEPLOYMENT_ID",
            agent_deployment.id,
        )
        pulumi.export(
            "Agent Deployment Chat Endpoint " + base.agent_asset_name,
            deployment_completions_endpoint,
        )

    app_runtime_parameters = [
        pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
            key=base.agent_application_name.upper() + "_DEPLOYMENT_ID",
            type="string",
            value=agent_deployment_id,
        ),
        pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
            key=base.agent_application_name.upper() + "_ENDPOINT",
            type="string",
            value=deployment_endpoint,
        ),
    ]

    agent_runtime_parameters = [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=base.agent_application_name.upper() + "_DEPLOYMENT_ID",
            type="string",
            value=agent_deployment_id,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=base.agent_application_name.upper() + "_ENDPOINT",
            type="string",
            value=deployment_endpoint,
        ),
    ]
    if base.IS_A2A_SERVER_ENABLED:
        agent_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=base.agent_application_name.upper() + "_A2A_ENDPOINT",
                type="string",
                value=deployment_a2a_endpoint,
            ),
        )

    return {
        "execution_environment": execution_environment,
        "deployment": agent_deployment,
        "workload": None,
        "custom_model": custom_model,
        "agent_deployment_id": agent_deployment_id,
        "prediction_environment": prediction_environment,
        "registered_model_args": registered_model_args,
        "deployment_args": deployment_args,
        "playground": playground,
        "agent_serving_endpoint": deployment_endpoint,
        "agent_a2a_endpoint": (
            deployment_a2a_endpoint if base.IS_A2A_SERVER_ENABLED else None
        ),
        "app_runtime_parameters": app_runtime_parameters,
        "agent_runtime_parameters": agent_runtime_parameters,
    }
