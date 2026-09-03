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
from typing import Any, Final, cast

import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi.stack import PROJECT_NAME

SESSION_SECRET_KEY: Final[str] = "SESSION_SECRET_KEY"
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

# (env var name, credential) pairs mirroring custom_model_runtime_parameters,
# consumed by the workload path as "dr-credential" env var references.
workload_env_var_credentials: list[tuple[str, pulumi_datarobot.ApiTokenCredential]] = []

# Field holding the token inside a DataRobot api_token credential; used as the
# `key` of "dr-credential" env var references in Workload artifact specs.
DR_CREDENTIAL_API_TOKEN_KEY: Final[str] = "apiToken"


def _register_credential(
    key: str, credential: pulumi_datarobot.ApiTokenCredential
) -> None:
    custom_model_runtime_parameters.append(
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=key,
            type="credential",
            value=credential.id,
        ),
    )
    workload_env_var_credentials.append((key, credential))


def dr_credential_env_var(name: str, credential_id: Any) -> dict[str, str]:
    """Workload artifact env var entry resolved from a DataRobot credential at runtime.

    Uses wire-format (camelCase) keys: entries are posted to the Workload API
    as-is, so the credential value itself never appears in the artifact spec or
    Pulumi state.
    """
    return {
        "name": name,
        "source": "dr-credential",
        "drCredentialId": cast(str, credential_id),
        "key": DR_CREDENTIAL_API_TOKEN_KEY,
    }


def workload_credential_env_vars() -> list[dict[str, str]]:
    """dr-credential env vars for the same API keys the deployment path registers."""
    return [
        dr_credential_env_var(key, credential.id)
        for key, credential in workload_env_var_credentials
    ]


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
    _register_credential(PERPLEXITY_API_KEY, _perplexity_cred)

if _auth_resolution_strategy == "config" and _tavily_tools_enabled() and _tavily_value:
    pulumi.info(
        "Tavily API key found; registering as an MCP server runtime credential."
    )
    _tavily_cred = pulumi_datarobot.ApiTokenCredential(
        f"[{PROJECT_NAME}] Tavily API Key",
        args=pulumi_datarobot.ApiTokenCredentialArgs(api_token=_tavily_value),
    )
    _register_credential(TAVILY_API_KEY, _tavily_cred)

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
    _register_credential(ATLASSIAN_API_TOKEN, _atlassian_cred)

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
        _register_credential(ATLASSIAN_EMAIL, _atlassian_email_cred)

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
        _register_credential(ATLASSIAN_SITE_URL, _atlassian_site_url_cred)
