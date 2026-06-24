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
"""Optional Perplexity / Tavily / Atlassian keys for the MCP server (injected as runtime credentials)."""

import os
from typing import Final

import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

PERPLEXITY_API_KEY: Final[str] = "PERPLEXITY_API_KEY"
TAVILY_API_KEY: Final[str] = "TAVILY_API_KEY"
ATLASSIAN_API_TOKEN: Final[str] = "ATLASSIAN_API_TOKEN"
ATLASSIAN_EMAIL: Final[str] = "ATLASSIAN_EMAIL"
ATLASSIAN_SITE_URL: Final[str] = "ATLASSIAN_SITE_URL"
AUTH_RESOLUTION_STRATEGY: Final[str] = "AUTH_RESOLUTION_STRATEGY"
MCP_CLI_CONFIGS: Final[str] = "MCP_CLI_CONFIGS"
ENABLE_JIRA_TOOLS: Final[str] = "ENABLE_JIRA_TOOLS"
ENABLE_CONFLUENCE_TOOLS: Final[str] = "ENABLE_CONFLUENCE_TOOLS"
ENABLE_PERPLEXITY_TOOLS: Final[str] = "ENABLE_PERPLEXITY_TOOLS"
ENABLE_TAVILY_TOOLS: Final[str] = "ENABLE_TAVILY_TOOLS"
CONFIG_AUTH: Final[str] = "config_auth"

_perplexity_value = (os.environ.get(PERPLEXITY_API_KEY) or "").strip()
_tavily_value = (os.environ.get(TAVILY_API_KEY) or "").strip()
_atlassian_value = (os.environ.get(ATLASSIAN_API_TOKEN) or "").strip()
_atlassian_email_value = (os.environ.get(ATLASSIAN_EMAIL) or "").strip()
_atlassian_site_url_value = (os.environ.get(ATLASSIAN_SITE_URL) or "").strip()


def _parse_mcp_cli_configs() -> set[str]:
    raw = (os.environ.get(MCP_CLI_CONFIGS) or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def auth_resolution_strategy() -> str:
    """Resolve auth mode from AUTH_RESOLUTION_STRATEGY or MCP_CLI_CONFIGS config_auth."""
    explicit = (os.environ.get(AUTH_RESOLUTION_STRATEGY) or "").strip().lower()
    if explicit:
        return explicit
    if CONFIG_AUTH in _parse_mcp_cli_configs():
        return "config"
    return "http"


_auth_resolution_strategy = auth_resolution_strategy()


def _atlassian_tools_enabled() -> bool:
    if (os.environ.get(ENABLE_JIRA_TOOLS) or "").strip().lower() == "true":
        return True
    if (os.environ.get(ENABLE_CONFLUENCE_TOOLS) or "").strip().lower() == "true":
        return True
    configs = _parse_mcp_cli_configs()
    return "jira" in configs or "confluence" in configs


def _perplexity_tools_enabled() -> bool:
    if (os.environ.get(ENABLE_PERPLEXITY_TOOLS) or "").strip().lower() == "true":
        return True
    return "perplexity" in _parse_mcp_cli_configs()


def _tavily_tools_enabled() -> bool:
    if (os.environ.get(ENABLE_TAVILY_TOOLS) or "").strip().lower() == "true":
        return True
    return "tavily" in _parse_mcp_cli_configs()


custom_model_runtime_parameters: list[
    pulumi_datarobot.CustomModelRuntimeParameterValueArgs
] = []

if (
    _auth_resolution_strategy == "config"
    and _perplexity_tools_enabled()
    and _perplexity_value
):
    pulumi.info(
        "Perplexity API key found; registering as an MCP server runtime credential."
    )
    _perplexity_cred = pulumi_datarobot.ApiTokenCredential(
        f"[{PROJECT_NAME}] Perplexity API Key",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=_perplexity_value),
    )
    custom_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=PERPLEXITY_API_KEY,
            type="credential",
            value=_perplexity_cred.id,
        ),
    )

if _auth_resolution_strategy == "config" and _tavily_tools_enabled() and _tavily_value:
    pulumi.info(
        "Tavily API key found; registering as an MCP server runtime credential."
    )
    _tavily_cred = pulumi_datarobot.ApiTokenCredential(
        f"[{PROJECT_NAME}] Tavily API Key",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=_tavily_value),
    )
    custom_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=TAVILY_API_KEY,
            type="credential",
            value=_tavily_cred.id,
        ),
    )

if (
    _auth_resolution_strategy == "config"
    and _atlassian_tools_enabled()
    and _atlassian_value
):
    pulumi.info(
        "Atlassian API token found; registering as an MCP server runtime credential."
    )
    _atlassian_cred = pulumi_datarobot.ApiTokenCredential(
        f"[{PROJECT_NAME}] Atlassian API Token",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=_atlassian_value),
    )
    custom_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=ATLASSIAN_API_TOKEN,
            type="credential",
            value=_atlassian_cred.id,
        ),
    )

    if _atlassian_email_value:
        pulumi.info(
            "Atlassian email found; registering as an MCP server runtime credential."
        )
        _atlassian_email_cred = pulumi_datarobot.ApiTokenCredential(
            f"[{PROJECT_NAME}] Atlassian Email",
            args=pulumi_datarobot.ApiTokenCredentialArgs(
                api_token=_atlassian_email_value
            ),
        )
        custom_model_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=ATLASSIAN_EMAIL,
                type="credential",
                value=_atlassian_email_cred.id,
            ),
        )

    if _atlassian_site_url_value:
        pulumi.info(
            "Atlassian site URL found; registering as an MCP server runtime credential."
        )
        _atlassian_site_url_cred = pulumi_datarobot.ApiTokenCredential(
            f"[{PROJECT_NAME}] Atlassian Site URL",
            args=pulumi_datarobot.ApiTokenCredentialArgs(
                api_token=_atlassian_site_url_value
            ),
        )
        custom_model_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=ATLASSIAN_SITE_URL,
                type="credential",
                value=_atlassian_site_url_cred.id,
            ),
        )
