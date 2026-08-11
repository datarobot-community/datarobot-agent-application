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
from dataclasses import dataclass
from typing import TypedDict

from pulumi_datarobot import (
    UserMcpPromptMetadata as UserMcpPromptMetadataPulumiResource,
)
from pulumi_datarobot import (
    UserMcpResourceMetadata as UserMcpResourceMetadataPulumiResource,
)
from pulumi_datarobot import UserMcpToolMetadata as UserMcpToolMetadataPulumiResource

from dev_tools.lineage.enums import (
    DataRobotMCPPromptCategory,
    DataRobotMCPResourceCategory,
    DataRobotMCPToolCategory,
)


class MCPToolMetadataDictType(TypedDict):
    name: str
    type: str


class MCPPromptMetadataDictType(TypedDict):
    name: str
    type: str


class MCPResourceMetadataDictType(TypedDict):
    name: str
    type: str
    uri: str


@dataclass(frozen=True)
class MCPToolMetadata:
    name: str
    type: DataRobotMCPToolCategory

    @classmethod
    def from_dict(cls, metadata_in_dict: MCPToolMetadataDictType) -> "MCPToolMetadata":
        return cls(
            metadata_in_dict["name"],
            DataRobotMCPToolCategory.from_string(metadata_in_dict["type"]),
        )


@dataclass(frozen=True)
class MCPPromptMetadata:
    name: str
    type: DataRobotMCPPromptCategory

    @classmethod
    def from_dict(
        cls, metadata_in_dict: MCPPromptMetadataDictType
    ) -> "MCPPromptMetadata":
        return cls(
            metadata_in_dict["name"],
            DataRobotMCPPromptCategory.from_string(metadata_in_dict["type"]),
        )


@dataclass(frozen=True)
class MCPResourceMetadata:
    name: str
    type: DataRobotMCPResourceCategory
    uri: str

    @classmethod
    def from_dict(
        cls, metadata_in_dict: MCPResourceMetadataDictType
    ) -> "MCPResourceMetadata":
        return cls(
            metadata_in_dict["name"],
            DataRobotMCPResourceCategory.from_string(metadata_in_dict["type"]),
            metadata_in_dict["uri"],
        )


@dataclass(frozen=True)
class MCPToolMetadataPulumiResourceCreateOutput:
    name: str
    pulumi_resource: UserMcpToolMetadataPulumiResource


@dataclass(frozen=True)
class MCPPromptMetadataPulumiResourceCreateOutput:
    name: str
    pulumi_resource: UserMcpPromptMetadataPulumiResource


@dataclass(frozen=True)
class MCPResourceMetadataPulumiResourceCreateOutput:
    name: str
    pulumi_resource: UserMcpResourceMetadataPulumiResource
