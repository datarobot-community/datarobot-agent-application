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
import re
from typing import Final

import pulumi
import pulumi_datarobot
import datarobot as dr
from datarobot_pulumi_utils.pulumi import resolve_execution_environment_version
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME
from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments
from dev_tools.lineage.pulumi_managers import MCPToolMetadataPulumiManager
from dev_tools.lineage.pulumi_managers import MCPPromptMetadataPulumiManager
from dev_tools.lineage.pulumi_managers import MCPResourceMetadataPulumiManager

from . import project_dir, use_case

from .mcp_server_user_params import MCP_USER_RUNTIME_PARAMETERS
from .mcp_server_api_keys import (
    auth_resolution_strategy,
    custom_model_runtime_parameters as api_keys_runtime_parameters,
)

DEFAULT_EXECUTION_ENVIRONMENT = "Python 3.11 GenAI Agents"

EXCLUDE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        # Test and development files
        r".*tests/.*",
        r".*\.coverage",
        r".*coverage\.xml",
        r".*coveragerc",
        r".*htmlcov/.*",
        r".*env",
        r".pre-commit-config.yaml",
        # Cache and temporary files
        r".*\.DS_Store",
        r".*\.pyc",
        r".*\.pyo",
        r".*\.pyd",
        r".*\.ruff_cache/.*",
        r".*\.venv/.*",
        r".*\.mypy_cache/.*",
        r".*__pycache__/.*",
        r".*\.pytest_cache/.*",
        r".*\.tox/.*",
        r".*\.nox/.*",
        r".*\.uv/.*",
        # Documentation and examples
        r".*docs/.*",
        r".*examples/.*",
        r".*samples/.*",
        r".*\.md$",
        r".*\.rst$",
        r".*\.txt$",
        # IDE and editor files
        r".*\.vscode/.*",
        r".*\.idea/.*",
        r".*\.sublime-.*",
        r".*\.vim/.*",
        # OS specific files
        r".*Thumbs\.db",
        r".*desktop\.ini",
        r".*\.swp",
        r".*\.swo",
        r".*~$",
        # Build artifacts
        r".*build/.*",
        r".*dist/.*",
        r".*egg-info/.*",
        r".*\.egg/.*",
        # Logs
        r".*\.log$",
        r".*logs/.*",
    ]
]


__all__ = [
    "execution_environment",
    "deployment",
    "mcp_server_mcp_endpoint",
    "mcp_server_base_endpoint",
    "mcp_custom_model_runtime_parameters",
]

mcp_server_asset_name: str = f"[{PROJECT_NAME}] [mcp_server]"

deployments_application_path = project_dir.parent / "mcp_server"


def get_deployments_app_files() -> list[tuple[str, str]]:
    # Essential files only - whitelist approach to stay under 100 file limit
    essential_files = [
        "app/",
        "pyproject.toml",
        "uv.lock",
    ]
    source_files = []
    # Add essential files
    for essential_file in essential_files:
        file_path = deployments_application_path / essential_file
        if file_path.exists():
            if file_path.is_file():
                source_files.append((str(file_path), essential_file))
            elif file_path.is_dir():
                # Add all Python files from app directory only
                for py_file in file_path.rglob("*.py"):
                    if py_file.is_file():
                        rel_path = py_file.relative_to(deployments_application_path)
                        source_files.append((str(py_file), str(rel_path)))

    # Filter out any files that match exclude patterns (safety check)
    source_files = [
        (file_path, file_name)
        for file_path, file_name in source_files
        if not any(
            exclude_pattern.match(file_name) for exclude_pattern in EXCLUDE_PATTERNS
        )
    ]

    # Remove duplicates based on file_name (relative path)
    seen_files = set()
    unique_source_files = []
    for file_path_, file_name in source_files:
        if file_name not in seen_files:
            seen_files.add(file_name)
            unique_source_files.append((file_path_, file_name))
    return unique_source_files


# Start of Pulumi settings and application infrastructure
_dr_exec_env = os.environ.get("DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", "").strip()
if len(_dr_exec_env) > 0:
    # Get the default execution environment from environment variable
    execution_environment_id = _dr_exec_env
    if DEFAULT_EXECUTION_ENVIRONMENT in execution_environment_id:
        pulumi.info("Using default GenAI Agentic Execution Environment.")
        execution_environment_id = RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.id

    execution_environment_version_id = resolve_execution_environment_version(
        execution_environment_id,
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT_VERSION_ID",
    )

    pulumi.info(
        "Using existing execution environment: "
        + execution_environment_id
        + " Version ID: "
        + str(execution_environment_version_id)
    )

    execution_environment = pulumi_datarobot.ExecutionEnvironment.get(
        id=execution_environment_id,
        version_id=execution_environment_version_id,
        resource_name=mcp_server_asset_name + " Execution Environment",
    )
else:
    pulumi.info("Using docker folder to compile the execution environment")
    execution_environment = pulumi_datarobot.ExecutionEnvironment(
        resource_name=mcp_server_asset_name + " Execution Environment",
        name=mcp_server_asset_name,
        description="Execution environment for MCP server",
        programming_language="python",
        use_cases=["customModel"],
        docker_context_path=str(project_dir.parent / "mcp_server" / "docker"),
        opts=pulumi.ResourceOptions(retain_on_delete=False),
    )


def _parse_mcp_cli_enabled_set() -> set[str] | None:
    """Parse MCP_CLI_CONFIGS for deployment runtime params.

    - Not set → None (use defaults for each option).
    - Set but empty → empty set (user disabled all; all options false).
    - Set and non-empty → set of enabled option names (e.g. {'predictive', 'gdrive'}).
    """
    if "MCP_CLI_CONFIGS" not in os.environ:
        return None
    raw = os.environ["MCP_CLI_CONFIGS"].strip() if os.environ["MCP_CLI_CONFIGS"] else ""
    if not raw:
        return set()
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


_mcp_cli_enabled_set: set[str] | None = _parse_mcp_cli_enabled_set()


def _bool_from_env_or_cli(env_key: str, mcp_opt: str, default: str) -> str:
    """Use individual env var if set, else derive from MCP_CLI_CONFIGS, else default."""
    if env_key in os.environ and os.environ[env_key].strip():
        return str(os.environ[env_key]).lower()
    if _mcp_cli_enabled_set is not None:
        return "true" if mcp_opt in _mcp_cli_enabled_set else "false"
    return default


def _enabled_tools_runtime_params() -> list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
]:
    """Build enable_* tool params; individual ENABLE_* env vars take precedence over MCP_CLI_CONFIGS."""
    return [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_predictive_tools",
            type="boolean",
            value=_bool_from_env_or_cli(
                "ENABLE_PREDICTIVE_TOOLS", "predictive", "false"
            ),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_jira_tools",
            type="boolean",
            value=_bool_from_env_or_cli("ENABLE_JIRA_TOOLS", "jira", "false"),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_confluence_tools",
            type="boolean",
            value=_bool_from_env_or_cli(
                "ENABLE_CONFLUENCE_TOOLS", "confluence", "false"
            ),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_gdrive_tools",
            type="boolean",
            value=_bool_from_env_or_cli("ENABLE_GDRIVE_TOOLS", "gdrive", "false"),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_microsoft_graph_tools",
            type="boolean",
            value=_bool_from_env_or_cli(
                "ENABLE_MICROSOFT_GRAPH_TOOLS", "microsoft_graph", "false"
            ),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_perplexity_tools",
            type="boolean",
            value=_bool_from_env_or_cli(
                "ENABLE_PERPLEXITY_TOOLS", "perplexity", "false"
            ),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="enable_tavily_tools",
            type="boolean",
            value=_bool_from_env_or_cli("ENABLE_TAVILY_TOOLS", "tavily", "false"),
        ),
    ]


def _dynamic_registration_runtime_params() -> list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
]:
    """Build dynamic tools/prompts params; individual env vars take precedence over MCP_CLI_CONFIGS."""
    return [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="mcp_server_register_dynamic_tools_on_startup",
            type="boolean",
            value=_bool_from_env_or_cli(
                "MCP_SERVER_REGISTER_DYNAMIC_TOOLS_ON_STARTUP",
                "dynamic_tools",
                "false",
            ),
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="mcp_server_register_dynamic_prompts_on_startup",
            type="boolean",
            value=_bool_from_env_or_cli(
                "MCP_SERVER_REGISTER_DYNAMIC_PROMPTS_ON_STARTUP",
                "dynamic_prompts",
                "false",
            ),
        ),
    ]


# Custom Model
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
    *_dynamic_registration_runtime_params(),
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
        key="otel_attributes", type="string", value=os.getenv("OTEL_ATTRIBUTES", "{}")
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
    *_enabled_tools_runtime_params(),
]


# Session secret key credential.
SESSION_SECRET_KEY: Final[str] = "SESSION_SECRET_KEY"

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
    pulumi.export(SESSION_SECRET_KEY, session_secret_key)


# Only add optional OTEL parameters if they have values
if otel_collector_base_url := os.getenv("OTEL_COLLECTOR_BASE_URL"):
    deployments_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key="otel_collector_base_url", type="string", value=otel_collector_base_url
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
    resource_bundle_id="cpu.small",  # Use API /mlops/compute/bundles/?useCases=customModel to get list of available bundles
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
    pulumi.info(f"Using existing prediction environment '{prediction_environment_id}'")

    base_prediction_environment = pulumi_datarobot.PredictionEnvironment.get(
        id=prediction_environment_id,
        resource_name=mcp_server_asset_name + " Prediction Environment [PRE-EXISTING]",
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
mcp_resource_metadata_entities = mcp_resource_metadata_pulumi_manager.load_metadata()
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
