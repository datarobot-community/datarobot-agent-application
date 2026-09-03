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

"""Shared MCP_CLI_CONFIGS parsing for deployment and workload provisioning."""

from __future__ import annotations

import os

# (env_var_name, mcp_cli_option_name)
TOOL_FLAGS: list[tuple[str, str]] = [
    ("ENABLE_PREDICTIVE_TOOLS", "predictive"),
    ("ENABLE_JIRA_TOOLS", "jira"),
    ("ENABLE_CONFLUENCE_TOOLS", "confluence"),
    ("ENABLE_GDRIVE_TOOLS", "gdrive"),
    ("ENABLE_MICROSOFT_GRAPH_TOOLS", "microsoft_graph"),
    ("ENABLE_PERPLEXITY_TOOLS", "perplexity"),
    ("ENABLE_TAVILY_TOOLS", "tavily"),
    ("ENABLE_DR_DOCS_TOOLS", "dr_docs"),
]

DYNAMIC_FLAGS: list[tuple[str, str]] = [
    ("MCP_SERVER_REGISTER_DYNAMIC_TOOLS_ON_STARTUP", "dynamic_tools"),
    ("MCP_SERVER_REGISTER_DYNAMIC_PROMPTS_ON_STARTUP", "dynamic_prompts"),
]


def parse_mcp_cli_enabled_set() -> set[str] | None:
    """Parse MCP_CLI_CONFIGS into a set of enabled option names.

    - Not set → None (use per-option defaults).
    - Set but empty → empty set (user disabled all).
    - Set and non-empty → {'predictive', 'gdrive', ...}.
    """
    if "MCP_CLI_CONFIGS" not in os.environ:
        return None
    raw = os.environ["MCP_CLI_CONFIGS"].strip() if os.environ["MCP_CLI_CONFIGS"] else ""
    if not raw:
        return set()
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def bool_from_env_or_cli(
    env_key: str, mcp_opt: str, default: str, enabled_set: set[str] | None
) -> str:
    """Individual env var takes precedence; else derive from MCP_CLI_CONFIGS; else default."""
    if env_key in os.environ and os.environ[env_key].strip():
        return str(os.environ[env_key]).lower()
    if enabled_set is not None:
        return "true" if mcp_opt in enabled_set else "false"
    return default


def tool_flag_env_vars() -> list[dict[str, str]]:
    """Build container env-var entries for tool + dynamic-registration flags."""
    enabled_set = parse_mcp_cli_enabled_set()
    return [
        {
            "name": env_key,
            "value": bool_from_env_or_cli(env_key, mcp_opt, "false", enabled_set),
        }
        for env_key, mcp_opt in (*TOOL_FLAGS, *DYNAMIC_FLAGS)
    ]
