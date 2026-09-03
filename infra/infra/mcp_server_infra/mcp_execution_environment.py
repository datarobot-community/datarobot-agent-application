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

"""Shared MCP execution environment provisioning for deployment and workload paths."""

from __future__ import annotations

import os

import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi import resolve_execution_environment_version
from datarobot_pulumi_utils.schema.exec_envs import RuntimeEnvironments

from .. import project_dir
from .mcp_bundle import ensure_docker_build_context_files

DEFAULT_EXECUTION_ENVIRONMENT = "Python 3.11 GenAI Agents"

# Execution environment env vars (see .env.template and fixtures/e2e/use-cases.yaml):
#
# DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT
#   Selects an existing EE to reuse (ID or platform name). Skips the Docker build.
#
# DATAROBOT_MCP_EXECUTION_ENVIRONMENT_NAME
#   Only when DEFAULT is empty: names a new EE built from scratch from the app
#   Dockerfile. Optional — default is [{pulumi stack}] [{app name}]. Component
#   CI sets a stable name so ephemeral per-run stacks import/update one shared EE
#   (retain_on_delete) instead of creating a duplicate on every workflow run.


def _find_execution_environment_id_by_name(name: str) -> str | None:
    """Return the DataRobot id for a custom EE with an exact name match."""
    import datarobot as dr

    # search_for narrows server-side; the comprehension keeps only exact matches.
    matches = [
        environment
        for environment in dr.ExecutionEnvironment.list(search_for=name)
        if getattr(environment, "name", None) == name
    ]
    if not matches:
        return None
    if len(matches) > 1:
        pulumi.warn(
            "Found "
            + str(len(matches))
            + " execution environments named "
            + repr(name)
            + "; importing the most recently created"
        )
        matches.sort(
            key=lambda environment: getattr(environment, "created", "") or "",
            reverse=True,
        )
    return matches[0].id


def provision_mcp_execution_environment(
    mcp_server_asset_name: str,
    *,
    resource_name_suffix: str = "",
) -> pulumi_datarobot.ExecutionEnvironment:
    """
    Mirror datarobot-serverless execution environment selection:

    - ``DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT`` set → reference an existing EE
      by ID or platform name (skip Docker build entirely).
    - unset → build a new EE from the ``mcp_server`` app root via Pulumi.
      ``DATAROBOT_MCP_EXECUTION_ENVIRONMENT_NAME`` optionally sets the *name* of that
      new EE (not the same as DEFAULT, which selects an existing EE instead of building).
    """
    resource_label = (
        mcp_server_asset_name + resource_name_suffix + " Execution Environment"
    )
    _dr_exec_env = os.environ.get(
        "DATAROBOT_DEFAULT_MCP_EXECUTION_ENVIRONMENT", ""
    ).strip()

    if len(_dr_exec_env) > 0:
        execution_environment_id = _dr_exec_env
        if DEFAULT_EXECUTION_ENVIRONMENT in execution_environment_id:
            pulumi.info("Using default GenAI Agentic Execution Environment.")
            execution_environment_id = (
                RuntimeEnvironments.PYTHON_311_GENAI_AGENTS.value.id
            )

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

        return pulumi_datarobot.ExecutionEnvironment.get(
            id=execution_environment_id,
            version_id=execution_environment_version_id,
            resource_name=resource_label,
        )

    deployments_path = project_dir.parent / "mcp_server"
    ensure_docker_build_context_files(deployments_path)
    pulumi.info("Using app directory as Docker build context for execution environment")
    # Bound to a local so the line length does not depend on the app name this
    # template was rendered with (see the note in workload.py).
    docker_context_path = deployments_path
    ee_name_override = os.environ.get(
        "DATAROBOT_MCP_EXECUTION_ENVIRONMENT_NAME", ""
    ).strip()
    ee_name = ee_name_override or (mcp_server_asset_name + resource_name_suffix)
    existing_id: str | None = None
    if ee_name_override:
        pulumi.info("Using execution environment name override: " + ee_name_override)
        existing_id = _find_execution_environment_id_by_name(ee_name)
        if existing_id:
            pulumi.info(
                "Importing existing execution environment: "
                + existing_id
                + " (shared name "
                + ee_name
                + ")"
            )
    resource_opts = pulumi.ResourceOptions(
        retain_on_delete=bool(ee_name_override),
    )
    if existing_id:
        resource_opts = pulumi.ResourceOptions(
            import_=existing_id,
            retain_on_delete=True,
        )
    return pulumi_datarobot.ExecutionEnvironment(
        resource_name=resource_label,
        name=ee_name,
        description="Execution environment for MCP server",
        programming_language="python",
        use_cases=["customModel"],
        docker_context_path=str(docker_context_path),
        opts=resource_opts,
    )
