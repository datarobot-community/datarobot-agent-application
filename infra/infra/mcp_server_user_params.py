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
import os  # noqa # pylint: disable=unused-import

from infra.mcp_server_infra.mcp_utils import (
    MCPRuntimeParameter,
    MCPRuntimeParameterAPITokenCredential,
)

"""
# Example user configuration for MCP runtime parameters.
# This file is intended as a starting point for users to copy and modify.
# NOTE: Replace pulumi_datarobot.CustomModelRuntimeParameterValueArgs (type="string", ...) with MCPRuntimeParameter
# NOTE: Replace pulumi_datarobot.CustomModelRuntimeParameterValueArgs (type="credential") with MCPRuntimeParameterAPITokenCredential

MCP_USER_RUNTIME_PARAMETERS: list[MCPRuntimeParameter] = [
   MCPRuntimeParameter(
       name="user_name",
       value=os.getenv("USER_NAME", "default-user"),
       type="string",
    ),
]

MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS: list[MCPRuntimeParameterAPITokenCredential] = [
    MCPRuntimeParameterAPITokenCredential(
        name="dummy-api-token",
        value=os.getenv("DUMMY_API_TOKEN", "123abcd"),
    ),
]
"""

# Example parameter users can rename, remove, or extend.
MCP_USER_RUNTIME_PARAMETERS: list[MCPRuntimeParameter] = []

# Example credential users can rename, remove, or extend.
MCP_USER_CREDENTIAL_RUNTIME_PARAMETERS: list[MCPRuntimeParameterAPITokenCredential] = []
