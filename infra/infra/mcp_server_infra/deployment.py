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

"""MCP server provisioning via DataRobot Custom Model + Deployment."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import datarobot as dr
import pulumi
import pulumi_datarobot

from dev_tools.lineage.pulumi_managers import (
    MCPPromptMetadataPulumiManager,
    MCPResourceMetadataPulumiManager,
    MCPToolMetadataPulumiManager,
)

from .. import use_case
from ..mcp_server_user_params import MCP_USER_RUNTIME_PARAMETERS
from .mcp_api_keys import (
    SESSION_SECRET_KEY,
    auth_resolution_strategy,
)
from .mcp_api_keys import (
    custom_model_runtime_parameters as api_keys_runtime_parameters,
)
from .mcp_cli_configs import (
    DYNAMIC_FLAGS,
    TOOL_FLAGS,
    bool_from_env_or_cli,
    parse_mcp_cli_enabled_set,
)
from .mcp_execution_environment import provision_mcp_execution_environment
from .mcp_oauth_configs import (
    mcp_enable_unauthenticated_well_known_route_value,
    mcp_oauth_metadata_env_vars,
)


def _enabled_tools_runtime_params(
    mcp_cli_enabled_set: set[str] | None,
) -> list[pulumi_datarobot.CustomModelRuntimeParameterValueArgs]:
    return [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=env_key.lower(),
            type="boolean",
            value=bool_from_env_or_cli(env_key, mcp_opt, "false", mcp_cli_enabled_set),
        )
        for env_key, mcp_opt in TOOL_FLAGS
    ]


def _dynamic_registration_runtime_params(
    mcp_cli_enabled_set: set[str] | None,
) -> list[pulumi_datarobot.CustomModelRuntimeParameterValueArgs]:
    return [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=env_key.lower(),
            type="boolean",
            value=bool_from_env_or_cli(env_key, mcp_opt, "false", mcp_cli_enabled_set),
        )
        for env_key, mcp_opt in DYNAMIC_FLAGS
    ]


def provision_deployment_mcp_server(
    *,
    mcp_server_asset_name: str,
    get_deployments_app_files: Callable[[], list[tuple[str, str]]],
) -> dict[str, Any]:
    execution_environment = provision_mcp_execution_environment(mcp_server_asset_name)

    mcp_cli_enabled_set = parse_mcp_cli_enabled_set()

    deployments_model_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ] = [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="mcp_server_name",
            type="string",
            value=os.getenv("MCP_SERVER_NAME", "datarobot-mcp-server"),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="mcp_server_log_level",
            type="string",
            value=os.getenv("MCP_SERVER_LOG_LEVEL", "WARNING"),
        ),
        *_dynamic_registration_runtime_params(mcp_cli_enabled_set),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="tool_registration_duplicate_behavior",
            type="string",
            value=str(
                os.getenv("MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR", "warn")
            ).lower(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="tool_registration_allow_empty_schema",
            type="boolean",
            value=str(
                os.getenv("MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA", "false")
            ).lower(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="prompt_registration_duplicate_behavior",
            type="string",
            value=str(
                os.getenv("MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR", "warn")
            ).lower(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="app_log_level", type="string", value=os.getenv("APP_LOG_LEVEL", "INFO")
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="otel_attributes",
            type="string",
            value=os.getenv("OTEL_ATTRIBUTES", "{}"),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="otel_enabled",
            type="boolean",
            value=str(os.getenv("OTEL_ENABLED", "true")).lower(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="otel_enabled_http_instrumentors",
            type="boolean",
            value=str(os.getenv("OTEL_ENABLED_HTTP_INSTRUMENTORS", "false")).lower(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="auth_resolution_strategy",
            type="string",
            value=auth_resolution_strategy(),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="mcp_enable_unauthenticated_well_known_route",
            type="boolean",
            value=mcp_enable_unauthenticated_well_known_route_value(),
        ),
        *_enabled_tools_runtime_params(mcp_cli_enabled_set),
    ]

    # Session secret key credential.
    if session_secret_key := os.getenv(SESSION_SECRET_KEY):
        session_secret_cred = pulumi_datarobot.ApiTokenCredential(
            "MCP Server [mcp_server] Session Secret Key",
            args=pulumi_datarobot.ApiTokenCredentialArgs(
                api_token=str(session_secret_key),
            ),
        )
        deployments_model_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=SESSION_SECRET_KEY,
                type="credential",
                value=session_secret_cred.id,
            )
        )
        # Secret-wrapped so it is encrypted in state and hidden from plain
        # `pulumi stack output` (use --show-secrets to reveal).
        pulumi.export(SESSION_SECRET_KEY, pulumi.Output.secret(session_secret_key))

    # Only add optional OTEL parameters if they have values
    if otel_collector_base_url := os.getenv("OTEL_COLLECTOR_BASE_URL"):
        deployments_model_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="otel_collector_base_url",
                type="string",
                value=otel_collector_base_url,
            )
        )

    # Only add otel_entity_id if it is provided
    if otel_entity_id := os.getenv("OTEL_ENTITY_ID"):
        deployments_model_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="otel_entity_id",
                type="string",
                value=otel_entity_id,
            )
        )

    deployments_model_runtime_parameters.extend(MCP_USER_RUNTIME_PARAMETERS)
    deployments_model_runtime_parameters.extend(api_keys_runtime_parameters)
    # The server reads each metadata setting by its own name; the runtime
    # parameter key is the lower-cased env var, as everywhere else here.
    deployments_model_runtime_parameters.extend(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=env_var["name"].lower(),
            type="string",
            value=env_var["value"],
        )
        for env_var in mcp_oauth_metadata_env_vars()
    )
    custom_model_files = get_deployments_app_files()

    use_mcp = os.getenv("USE_MCP_TARGET_TYPE", "true").lower() == "true"
    if use_mcp:
        pulumi.info("Using MCP target_type")
        target_type = "MCP"
        target_name = None
    else:
        pulumi.info("Using unstructured target_type for older environment")
        target_type = "Unstructured"
        target_name = "resultText"

    custom_model = pulumi_datarobot.CustomModel(
        resource_name=mcp_server_asset_name + " Custom Model",
        name=mcp_server_asset_name,
        description="MCP server",
        language="python",
        base_environment_id=execution_environment.id,
        base_environment_version_id=execution_environment.version_id,
        target_type=target_type,
        target_name=target_name,
        resource_bundle_id="cpu.small",
        files=custom_model_files,
        use_case_ids=[use_case.id],
        runtime_parameter_values=deployments_model_runtime_parameters,
        tags=[
            pulumi_datarobot.CustomModelTagArgs(
                name="tool",
                value="MCP",
            ),
        ],
    )

    # Register the custom model so it can be deployed
    registerd_model = pulumi_datarobot.RegisteredModel(
        resource_name=mcp_server_asset_name + " Registered Model",
        name=mcp_server_asset_name,
        custom_model_version_id=custom_model.version_id,
        use_case_ids=[use_case.id],
    )

    # Where to run the custom model
    if prediction_environment_id := os.environ.get(
        "DATAROBOT_DEFAULT_PREDICTION_ENVIRONMENT"
    ):
        pulumi.info(
            f"Using existing prediction environment '{prediction_environment_id}'"
        )
        base_prediction_environment = pulumi_datarobot.PredictionEnvironment.get(
            id=prediction_environment_id,
            resource_name=mcp_server_asset_name
            + " Prediction Environment [PRE-EXISTING]",
        )
    else:
        base_prediction_environment = pulumi_datarobot.PredictionEnvironment(
            resource_name=mcp_server_asset_name + " Prediction Environment",
            name=mcp_server_asset_name,
            platform=dr.enums.PredictionEnvironmentPlatform.DATAROBOT_SERVERLESS,
            opts=pulumi.ResourceOptions(retain_on_delete=False),
        )

    # Deploy the registered custom model
    deployment = pulumi_datarobot.Deployment(
        resource_name=mcp_server_asset_name + " Deployment",
        label=mcp_server_asset_name,
        use_case_ids=[use_case.id],
        registered_model_version_id=registerd_model.version_id,
        prediction_environment_id=base_prediction_environment.id,
    )

    datarobot_endpoint = os.getenv("DATAROBOT_ENDPOINT", "").rstrip("/")
    mcp_server_mcp_endpoint = deployment.id.apply(
        lambda id: f"{datarobot_endpoint}/deployments/{id}/directAccess/mcp"
    )
    mcp_server_base_endpoint = deployment.id.apply(
        lambda id: f"{datarobot_endpoint}/deployments/{id}/directAccess/"
    )
    pulumi.export(mcp_server_asset_name + " Custom Model Id", custom_model.id)
    pulumi.export(mcp_server_asset_name + " Deployment Id", deployment.id)
    pulumi.export(
        mcp_server_asset_name + " MCP Server Base Endpoint", mcp_server_base_endpoint
    )
    pulumi.export(
        mcp_server_asset_name + " MCP Server MCP Endpoint", mcp_server_mcp_endpoint
    )

    mcp_custom_model_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ] = [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="MCP_DEPLOYMENT_ID",
            type="string",
            value=deployment.id.apply(lambda id: f"{id}"),
        )
    ]

    mcp_tool_metadata_pulumi_manager = MCPToolMetadataPulumiManager()
    mcp_tool_metadata_entities = mcp_tool_metadata_pulumi_manager.load_metadata()
    mcp_tool_metadata_pulumi_resources = (
        mcp_tool_metadata_pulumi_manager.create_pulumi_resources(
            mcp_tool_metadata_entities,
            mcp_server_asset_name,
            custom_model.version_id,
        )
    )
    mcp_tool_metadata_pulumi_manager.export_summary_to_pulumi_stack(
        mcp_server_asset_name,
        mcp_tool_metadata_pulumi_resources,
    )

    mcp_prompt_metadata_pulumi_manager = MCPPromptMetadataPulumiManager()
    mcp_prompt_metadata_entities = mcp_prompt_metadata_pulumi_manager.load_metadata()
    mcp_prompt_metadata_pulumi_resources = (
        mcp_prompt_metadata_pulumi_manager.create_pulumi_resources(
            mcp_prompt_metadata_entities,
            mcp_server_asset_name,
            custom_model.version_id,
        )
    )
    mcp_prompt_metadata_pulumi_manager.export_summary_to_pulumi_stack(
        mcp_server_asset_name,
        mcp_prompt_metadata_pulumi_resources,
    )

    mcp_resource_metadata_pulumi_manager = MCPResourceMetadataPulumiManager()
    mcp_resource_metadata_entities = (
        mcp_resource_metadata_pulumi_manager.load_metadata()
    )
    mcp_resource_metadata_pulumi_resources = (
        mcp_resource_metadata_pulumi_manager.create_pulumi_resources(
            mcp_resource_metadata_entities,
            mcp_server_asset_name,
            custom_model.version_id,
        )
    )
    mcp_resource_metadata_pulumi_manager.export_summary_to_pulumi_stack(
        mcp_server_asset_name,
        mcp_resource_metadata_pulumi_resources,
    )

    return {
        "execution_environment": execution_environment,
        "deployment": deployment,
        "mcp_server_mcp_endpoint": mcp_server_mcp_endpoint,
        "mcp_server_base_endpoint": mcp_server_base_endpoint,
        "mcp_custom_model_runtime_parameters": mcp_custom_model_runtime_parameters,
    }
