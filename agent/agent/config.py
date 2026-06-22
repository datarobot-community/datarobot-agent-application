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
All configuration for the agent application. The config class handles
loading variables from environment, .env files, Pulumi outputs, and
DataRobot credentials automatically.
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

    llm_deployment_id: str | None = None
    llm_default_model: str = "datarobot/azure/gpt-5-mini-2025-08-07"
    use_datarobot_llm_gateway: bool = False
    mcp_deployment_id: str | None = None
    external_mcp_url: str | None = None
    local_dev_port: int = Field(
        default=8842, validation_alias="AGENT_PORT", ge=1, le=65535
    )

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
