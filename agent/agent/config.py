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
# ------------------------------------------------------------------------------
"""
All configuration for the agent component. The config class handles
loading variables from environment, .env files, Pulumi outputs, and
DataRobot credentials automatically.

This is the authoritative configuration for the agent component. `datarobot-genai`
resolves the DataRobot connection and every LLM setting through this class instead
of its own defaults, so whatever is set here is what the agent runs with. Adding a
field here is all it takes to make it available; nothing needs to be registered.
"""

import os
from typing import Any

from datarobot.core.config import DataRobotAppFrameworkBaseSettings
from pydantic import Field, ValidationInfo, field_validator, model_validator


class Config(DataRobotAppFrameworkBaseSettings):  # type: ignore[misc]
    """
    This class finds variables in the priority order of: env
    variables (including Runtime Parameters), .env, file_secrets, then
    Pulumi output variables.
    """

    # DataRobot connection, shared by every LLM instance and DataRobot client.
    datarobot_endpoint: str = "https://app.datarobot.com/api/v2"
    datarobot_api_token: str | None = None

    # Settings for the "llm" LLM component instance, read from LLM_DEPLOYMENT_ID,
    # LLM_DEFAULT_MODEL and so on. A second LLM component brings its own set of
    # these fields under its own name.
    llm_deployment_id: str | None = None
    llm_default_model: str = "datarobot/azure/gpt-5-mini-2025-08-07"
    llm_nim_deployment_id: str | None = None
    llm_use_datarobot_llm_gateway: bool = True

    mcp_deployment_id: str | None = None
    external_mcp_url: str | None = None
    local_dev_port: int = Field(
        default=8842, validation_alias="AGENT_PORT", ge=1, le=65535
    )

    # Prior conversation messages replayed to the agent. 0 disables history.
    max_history_messages: int = Field(
        default=20, ge=0, alias="datarobot_genai_max_history_messages"
    )
    # CrewAI only: report native tool-calling support for NIM models that LiteLLM has no
    # catalog entry for, so CrewAI uses API tool calls instead of the ReAct path.
    assume_native_tool_calling_when_unmapped: bool = False

    otel_entity_id: str = ""
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""

    @field_validator("otel_exporter_otlp_headers", mode="before")
    @classmethod
    def _assemble_otel_headers(cls, v: object, info: ValidationInfo) -> object:
        if v:
            return v
        entity_id = (info.data or {}).get("otel_entity_id", "")
        api_token = os.environ.get("DATAROBOT_API_TOKEN", "")
        if entity_id and api_token:
            return f"x-datarobot-entity-id={entity_id},x-datarobot-api-key={api_token}"
        return v

    @model_validator(mode="before")
    @classmethod
    def replace_placeholder_values(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field_name, field_info in cls.model_fields.items():
                if data.get(field_name) == "SET_VIA_PULUMI_OR_MANUALLY":
                    data[field_name] = field_info.default
        return data
