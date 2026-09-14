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
import sys
from typing import Final

import pulumi
import pulumi_datarobot  # noqa: F401 — re-exported for unit tests
from datarobot_pulumi_utils.pulumi import resolve_execution_environment_version
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

from dev_tools.lineage.pulumi_managers import (
    MCPPromptMetadataPulumiManager,
    MCPResourceMetadataPulumiManager,
    MCPToolMetadataPulumiManager,
)

from . import project_dir, use_case
from .mcp_server_infra.deployment import (
    provision_deployment_mcp_server,
)
from .mcp_server_infra.mcp_bundle import FileBundler, normalize_shell_scripts
from .mcp_server_infra.mcp_execution_environment import (
    provision_mcp_execution_environment,
)
from .mcp_server_infra.workload import (
    WorkloadBuilder,
    WorkloadConfiguration,
    WorkloadGeneratedDockerfileManager,
    WorkloadProvidedDockerfileManager,
    WorkloadProvider,
    provision_workload_mcp_server,
    provision_workload_mcp_server_from_image_uri,
)

__all__ = [
    "MCPPromptMetadataPulumiManager",
    "MCPResourceMetadataPulumiManager",
    "MCPToolMetadataPulumiManager",
    "deployment",
    "execution_environment",
    "mcp_custom_model_runtime_parameters",
    "mcp_server_base_endpoint",
    "mcp_server_mcp_endpoint",
    "resolve_execution_environment_version",
    "use_case",
]

mcp_server_asset_name: str = f"[{PROJECT_NAME}] [mcp_server]"

deployments_application_path = project_dir.parent / "mcp_server"

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


MCP_DEPLOYMENT_TYPE_SERVERLESS: Final[str] = "datarobot-serverless"
MCP_DEPLOYMENT_TYPE_WORKLOAD_PREVIEW: Final[str] = "datarobot-workload-preview"
MCP_DEPLOYMENT_TYPE_WORKLOAD: Final[str] = "datarobot-workload"
INVALID_MCP_DEPLOYMENT_TYPE: Final[str] = "not-found-mcp-deployment-type"


class InitialConfiguration:
    def __init__(self, configuration_var: str):
        self.configuration_var = configuration_var.strip().lower()
        self._truthy_values: Final[frozenset[str]] = frozenset({"true"})
        self._falsy_values: Final[frozenset[str]] = frozenset({"false"})

    def _resolve_enable_mcp_on_workload_api(self) -> bool:
        default = False
        if not self.configuration_var:
            pulumi.info(
                f"ENABLE_MCP_ON_WORKLOAD_API is not present — defaulted to {default}."
            )
            return default
        if self.configuration_var in self._truthy_values:
            pulumi.info("ENABLE_MCP_ON_WORKLOAD_API value resolved to true.")
            return True
        if self.configuration_var in self._falsy_values:
            pulumi.info("ENABLE_MCP_ON_WORKLOAD_API value resolved to false.")
            return False
        pulumi.error(
            "ENABLE_MCP_ON_WORKLOAD_API user's value is invalid, it should be true or false."
        )
        sys.exit(1)

    def resolve_mcp_deployment_type(self) -> str:
        workload_deployment_enabled = self._resolve_enable_mcp_on_workload_api()
        if workload_deployment_enabled:
            return MCP_DEPLOYMENT_TYPE_WORKLOAD
        return MCP_DEPLOYMENT_TYPE_SERVERLESS


enable_mcp_on_workload_api = os.getenv("ENABLE_MCP_ON_WORKLOAD_API", "")
setup = InitialConfiguration(enable_mcp_on_workload_api)
MCP_DEPLOYMENT_TYPE = setup.resolve_mcp_deployment_type()

pulumi.export(mcp_server_asset_name + " MCP_DEPLOYMENT_TYPE", MCP_DEPLOYMENT_TYPE)


def get_deployments_app_files() -> list[tuple[str, str]]:
    # Essential files only - whitelist approach to stay under 100 file limit
    essential_files = [
        "app/",
        "start_server.sh",
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
                        source_files.append((str(py_file), rel_path.as_posix()))

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
    return normalize_shell_scripts(unique_source_files)


if MCP_DEPLOYMENT_TYPE in {
    MCP_DEPLOYMENT_TYPE_WORKLOAD_PREVIEW,
    MCP_DEPLOYMENT_TYPE_WORKLOAD,
}:
    env_workload_mcp_image_uri = os.getenv("MCP_WORKLOAD_IMAGE_URI", "").strip()
    if env_workload_mcp_image_uri:
        _mcp_exports = provision_workload_mcp_server_from_image_uri(
            mcp_server_asset_name=mcp_server_asset_name,
            workload_image_uri=env_workload_mcp_image_uri,
        )
    else:
        # it is a C2W (code to workload) deployment
        if MCP_DEPLOYMENT_TYPE == MCP_DEPLOYMENT_TYPE_WORKLOAD_PREVIEW:
            _mcp_exports = provision_workload_mcp_server(
                mcp_server_asset_name=mcp_server_asset_name,
                get_deployments_app_files=get_deployments_app_files,
            )
        elif MCP_DEPLOYMENT_TYPE == MCP_DEPLOYMENT_TYPE_WORKLOAD:
            workload_config = WorkloadConfiguration.from_os_env(mcp_server_asset_name)
            workload_builder = WorkloadBuilder(mcp_server_asset_name, workload_config)

            mcp_dir_abs_path = (
                deployments_application_path  # _deployments_application_path()
            )
            file_bundler = FileBundler(
                deployment_app_abs_path=mcp_dir_abs_path,
                project_dir_abs_path=project_dir,
            )
            dockerfile_relative_path = FileBundler.resolve_dockerfile_relative_path(
                deployment_app_abs_path=mcp_dir_abs_path
            )
            workload_manager: (
                WorkloadProvidedDockerfileManager
                | WorkloadGeneratedDockerfileManager
                | None
            ) = None
            if dockerfile_relative_path:
                workload_manager = WorkloadProvidedDockerfileManager(
                    mcp_server_asset_name,
                    dockerfile_relative_path,
                    file_bundler,
                    workload_builder,
                )
            else:
                # generated dockerfile
                execution_env = provision_mcp_execution_environment(
                    mcp_server_asset_name,
                    resource_name_suffix=" [Workload Generated Dockerfile]",
                )
                if execution_env:
                    workload_artifact_entrypoint = (
                        WorkloadConfiguration.resolve_workload_entrypoint()
                    )
                    workload_manager = WorkloadGeneratedDockerfileManager(
                        mcp_server_asset_name,
                        execution_env,
                        file_bundler,
                        workload_builder,
                        workload_artifact_entrypoint,
                    )
                else:
                    message = (
                        "Internal error: execution environment is required for Workload "
                        "DockerfileGenerated builds"
                    )
                    pulumi.error(message)
                    raise RuntimeError(message)
            workload_provider = WorkloadProvider(workload_manager)
            mcp_export = workload_provider.provision_mcp_server()
            _mcp_exports = mcp_export.to_dict()
else:
    _mcp_exports = provision_deployment_mcp_server(
        mcp_server_asset_name=mcp_server_asset_name,
        get_deployments_app_files=get_deployments_app_files,
    )

execution_environment = _mcp_exports["execution_environment"]
deployment = _mcp_exports["deployment"]
mcp_server_mcp_endpoint = _mcp_exports["mcp_server_mcp_endpoint"]
mcp_server_base_endpoint = _mcp_exports["mcp_server_base_endpoint"]
mcp_custom_model_runtime_parameters = _mcp_exports[
    "mcp_custom_model_runtime_parameters"
]
