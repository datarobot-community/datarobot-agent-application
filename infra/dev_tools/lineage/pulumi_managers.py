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
import os
from pathlib import Path
from typing import List
from typing import Set

import pulumi
import yaml  # type: ignore[import-untyped]

from pulumi_datarobot import UserMcpToolMetadata as UserMcpToolMetadataPulumiResource
from pulumi_datarobot import (
    UserMcpPromptMetadata as UserMcpPromptMetadataPulumiResource,
)
from pulumi_datarobot import (
    UserMcpResourceMetadata as UserMcpResourceMetadataPulumiResource,
)

from dev_tools.lineage.entities import MCPToolMetadata
from dev_tools.lineage.entities import MCPPromptMetadata
from dev_tools.lineage.entities import MCPResourceMetadata
from dev_tools.lineage.entities import MCPToolMetadataPulumiResourceCreateOutput
from dev_tools.lineage.entities import MCPPromptMetadataPulumiResourceCreateOutput
from dev_tools.lineage.entities import MCPResourceMetadataPulumiResourceCreateOutput


def get_mcp_item_metadata_dir_path() -> Path:
    current_path = Path(os.path.dirname(__file__))
    return (
        current_path.parent.parent.parent
        / "mcp_server"
        / "dev_tools"
        / "lineage"
        / "mcp_item_metadata"
    )


def get_mcp_tool_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_tools.yaml"


def get_mcp_prompt_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_prompts.yaml"


def get_mcp_resource_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_resources.yaml"


def load_from_yaml(yaml_path: Path) -> List[dict[str, str]]:
    with open(yaml_path, "r") as file:
        return yaml.safe_load(file) or []


class MCPToolMetadataPulumiManager:
    def __init__(self):
        self.metadata_file_path = get_mcp_tool_metadata_file_path()

    def load_metadata(self) -> Set[MCPToolMetadata]:
        metadata_list = load_from_yaml(self.metadata_file_path)
        return {MCPToolMetadata.from_dict(metadata) for metadata in metadata_list}  # type: ignore[arg-type]

    @staticmethod
    def get_pulumi_resource_name(
        resource_name: str,
        resource_name_prefix: str,
    ) -> str:
        return f"{resource_name_prefix} MCP tool metadata (name: {resource_name!r})"

    @classmethod
    def create_pulumi_resources(
        cls,
        metadata_entities: Set[MCPToolMetadata],
        resource_name_prefix: str,
        mcp_server_version_id: pulumi.Output[str],
    ) -> Set[MCPToolMetadataPulumiResourceCreateOutput]:
        outputs = set()
        for metadata in metadata_entities:
            resource_name = cls.get_pulumi_resource_name(
                metadata.name, resource_name_prefix
            )
            creation_output = MCPToolMetadataPulumiResourceCreateOutput(
                name=resource_name,
                pulumi_resource=UserMcpToolMetadataPulumiResource(
                    resource_name=resource_name,
                    name=metadata.name,
                    type=metadata.type.to_api_representation(),
                    mcp_server_version_id=mcp_server_version_id,
                ),
            )
            outputs.add(creation_output)
        return outputs

    @classmethod
    def export_to_pulumi_stack(
        cls,
        pulumi_resource_creation_outputs: Set[
            MCPToolMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        for pulumi_resource_creation_output in pulumi_resource_creation_outputs:
            pulumi.export(
                pulumi_resource_creation_output.name,
                pulumi_resource_creation_output.pulumi_resource.id,
            )

    @classmethod
    def export_summary_to_pulumi_stack(
        cls,
        resource_name_prefix: str,
        pulumi_resource_creation_outputs: Set[
            MCPToolMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        pulumi.export(
            f"{resource_name_prefix} Number of MCP tool metadata records created",
            len(pulumi_resource_creation_outputs),
        )


class MCPPromptMetadataPulumiManager:
    def __init__(self):
        self.metadata_file_path = get_mcp_prompt_metadata_file_path()

    def load_metadata(self) -> Set[MCPPromptMetadata]:
        metadata_list = load_from_yaml(self.metadata_file_path)
        return {MCPPromptMetadata.from_dict(metadata) for metadata in metadata_list}  # type: ignore[arg-type]

    @staticmethod
    def get_pulumi_resource_name(
        resource_name: str,
        resource_name_prefix: str,
    ) -> str:
        return f"{resource_name_prefix} MCP prompt metadata (name: {resource_name!r})"

    @classmethod
    def create_pulumi_resources(
        cls,
        metadata_entities: Set[MCPPromptMetadata],
        resource_name_prefix: str,
        mcp_server_version_id: pulumi.Output[str],
    ) -> Set[MCPPromptMetadataPulumiResourceCreateOutput]:
        outputs = set()
        for metadata in metadata_entities:
            resource_name = cls.get_pulumi_resource_name(
                metadata.name, resource_name_prefix
            )
            creation_output = MCPPromptMetadataPulumiResourceCreateOutput(
                name=resource_name,
                pulumi_resource=UserMcpPromptMetadataPulumiResource(
                    resource_name=resource_name,
                    name=metadata.name,
                    type=metadata.type.to_api_representation(),
                    mcp_server_version_id=mcp_server_version_id,
                ),
            )
            outputs.add(creation_output)
        return outputs

    @classmethod
    def export_to_pulumi_stack(
        cls,
        pulumi_resource_creation_outputs: Set[
            MCPPromptMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        for pulumi_resource_creation_output in pulumi_resource_creation_outputs:
            pulumi.export(
                pulumi_resource_creation_output.name,
                pulumi_resource_creation_output.pulumi_resource.id,
            )

    @classmethod
    def export_summary_to_pulumi_stack(
        cls,
        resource_name_prefix: str,
        pulumi_resource_creation_outputs: Set[
            MCPPromptMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        pulumi.export(
            f"{resource_name_prefix} Number of MCP prompt metadata records created",
            len(pulumi_resource_creation_outputs),
        )


class MCPResourceMetadataPulumiManager:
    def __init__(self):
        self.metadata_file_path = get_mcp_resource_metadata_file_path()

    def load_metadata(self) -> Set[MCPResourceMetadata]:
        metadata_list = load_from_yaml(self.metadata_file_path)
        return {MCPResourceMetadata.from_dict(metadata) for metadata in metadata_list}  # type: ignore[arg-type]

    @staticmethod
    def get_pulumi_resource_name(
        resource_name: str,
        resource_name_prefix: str,
    ) -> str:
        return f"{resource_name_prefix} MCP resource metadata (name: {resource_name!r})"

    @classmethod
    def create_pulumi_resources(
        cls,
        metadata_entities: Set[MCPResourceMetadata],
        resource_name_prefix: str,
        mcp_server_version_id: pulumi.Output[str],
    ) -> Set[MCPResourceMetadataPulumiResourceCreateOutput]:
        outputs = set()
        for metadata in metadata_entities:
            resource_name = cls.get_pulumi_resource_name(
                metadata.name, resource_name_prefix
            )
            creation_output = MCPResourceMetadataPulumiResourceCreateOutput(
                name=resource_name,
                pulumi_resource=UserMcpResourceMetadataPulumiResource(
                    resource_name=resource_name,
                    name=metadata.name,
                    type=metadata.type.to_api_representation(),
                    uri=metadata.uri,
                    mcp_server_version_id=mcp_server_version_id,
                ),
            )
            outputs.add(creation_output)
        return outputs

    @classmethod
    def export_to_pulumi_stack(
        cls,
        pulumi_resource_creation_outputs: Set[
            MCPResourceMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        for pulumi_resource_creation_output in pulumi_resource_creation_outputs:
            pulumi.export(
                pulumi_resource_creation_output.name,
                pulumi_resource_creation_output.pulumi_resource.id,
            )

    @classmethod
    def export_summary_to_pulumi_stack(
        cls,
        resource_name_prefix: str,
        pulumi_resource_creation_outputs: Set[
            MCPResourceMetadataPulumiResourceCreateOutput
        ],
    ) -> None:
        pulumi.export(
            f"{resource_name_prefix} Number of MCP resource metadata records created",
            len(pulumi_resource_creation_outputs),
        )
