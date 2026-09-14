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

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final

import pulumi
import pulumi_datarobot

DR_CREDENTIAL_API_TOKEN_KEY: Final[str] = "apiToken"


@dataclass
class PulumiOutputEndpoints:
    base_endpoint: str | pulumi.output.Output[str]
    mcp_endpoint: str | pulumi.output.Output[str]


@dataclass
class InfraProviderOutput:
    execution_environment: pulumi_datarobot.ExecutionEnvironment | None
    deployment: pulumi_datarobot.Deployment | None
    mcp_server_mcp_endpoint: str | pulumi.output.Output[str]
    mcp_server_base_endpoint: str | pulumi.output.Output[str]
    mcp_custom_model_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ]

    def to_dict(self):
        return {
            "execution_environment": self.execution_environment,
            "deployment": self.deployment,
            "mcp_server_mcp_endpoint": self.mcp_server_mcp_endpoint,
            "mcp_server_base_endpoint": self.mcp_server_base_endpoint,
            "mcp_custom_model_runtime_parameters": self.mcp_custom_model_runtime_parameters,
        }


class MCPAppEnvironmentVarNames(Enum):
    MCP_SERVER_NAME = auto()
    MCP_SERVER_LOG_LEVEL = auto()
    APP_LOG_LEVEL = auto()
    MCP_SERVER_TOOL_REGISTRATION_DUPLICATE_BEHAVIOR = auto()
    MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA = auto()
    MCP_SERVER_PROMPT_REGISTRATION_DUPLICATE_BEHAVIOR = auto()
    OTEL_ATTRIBUTES = auto()
    OTEL_ENABLED = auto()
    OTEL_ENABLED_HTTP_INSTRUMENTORS = auto()
    OTEL_COLLECTOR_BASE_URL = auto()
    OTEL_ENTITY_ID = auto()
    AUTH_RESOLUTION_STRATEGY = auto()  # requires method to evaluate
    # mcp cli config
    MCP_CLI_CONFIGS = auto()
    # oauth
    MCP_ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE = auto()
    MCP_ENABLE_OAUTH_CLAIM_VALIDATION = auto()
    # user_params_env_vars - mcp user runtime parameters
    USER_NAME = auto()
    #  session_secret
    SESSION_SECRET_KEY = auto()


@dataclass
class MCPRuntimeParameter:
    name: str
    value: str
    type: str = "string"

    def __post_init__(self):
        self.name = self.name.upper()


@dataclass
class MCPRuntimeParameterAPITokenCredential:
    name: str
    value: str
    type: str = field(init=False, default="credential")
    key: str = field(init=False, default=DR_CREDENTIAL_API_TOKEN_KEY)

    def __post_init__(self):
        self.name = self.name.upper()
