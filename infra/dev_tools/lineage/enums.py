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
from enum import Enum, auto

from datarobot.utils import camelize


class DataRobotMCPToolCategory(Enum):
    USER_TOOL = auto()  # tools created as mcp tool decorated python function by users
    BUILT_IN_TOOL = auto()  # tools as a wrapper of external service

    @staticmethod
    def from_string(enum_str: str) -> "DataRobotMCPToolCategory":
        enum_str_map = {
            "USER_TOOL": DataRobotMCPToolCategory.USER_TOOL,
            "BUILT_IN_TOOL": DataRobotMCPToolCategory.BUILT_IN_TOOL,
        }
        if enum_str not in enum_str_map:
            error_msg = f"Enum string should be one of {', '.join(enum_str_map.keys())}"
            raise ValueError(error_msg)

        return enum_str_map[enum_str]

    def to_api_representation(self) -> str:
        return camelize(self.name.lower())


class DataRobotMCPPromptCategory(Enum):
    USER_PROMPT_TEMPLATE = (
        auto()
    )  # prompt created as mcp prompt decorated python function by users

    @staticmethod
    def from_string(enum_str: str) -> "DataRobotMCPPromptCategory":
        enum_str_map = {
            "USER_PROMPT_TEMPLATE": DataRobotMCPPromptCategory.USER_PROMPT_TEMPLATE,
        }
        if enum_str not in enum_str_map:
            error_msg = f"Enum string should be one of {', '.join(enum_str_map.keys())}"
            raise ValueError(error_msg)

        return enum_str_map[enum_str]

    def to_api_representation(self) -> str:
        return camelize(self.name.lower())


class DataRobotMCPResourceCategory(Enum):
    USER_RESOURCE = (
        auto()
    )  # resource created as mcp resource decorated python function by users

    @staticmethod
    def from_string(enum_str: str) -> "DataRobotMCPResourceCategory":
        enum_str_map = {
            "USER_RESOURCE": DataRobotMCPResourceCategory.USER_RESOURCE,
        }
        if enum_str not in enum_str_map:
            error_msg = f"Enum string should be one of {', '.join(enum_str_map.keys())}"
            raise ValueError(error_msg)

        return enum_str_map[enum_str]

    def to_api_representation(self) -> str:
        return camelize(self.name.lower())
