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
from dataclasses import asdict
from pathlib import Path
from typing import Set

import yaml
from datarobot_genai.drmcp.core.dr_mcp_server import DataRobotMCPServer
from datarobot_genai.drmcp.core.mcp_instance import mcp

from dev_tools.lineage.entities import (
    UserMCPPromptMetadata,
    UserMCPResourceMetadata,
    UserMCPToolMetadata,
)


def get_mcp_app_dir_path() -> Path:
    current_path = Path(os.path.dirname(__file__))
    return Path(current_path.parent.parent) / "app"


def get_mcp_tool_dir_path() -> Path:
    return get_mcp_app_dir_path() / "tools"


def get_mcp_prompt_dir_path() -> Path:
    return get_mcp_app_dir_path() / "prompts"


def get_mcp_resource_dir_path() -> Path:
    return get_mcp_app_dir_path() / "resources"


def get_mcp_item_metadata_dir_path() -> Path:
    current_path = Path(os.path.dirname(__file__))
    return current_path.parent / "lineage" / "mcp_item_metadata"


def get_mcp_tool_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_tools.yaml"


def get_mcp_prompt_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_prompts.yaml"


def get_mcp_resource_metadata_file_path() -> Path:
    return get_mcp_item_metadata_dir_path() / "mcp_resources.yaml"


def get_dr_mcp_server_instance() -> DataRobotMCPServer:
    mcp_server = DataRobotMCPServer(
        mcp,
        additional_module_paths=[
            (str(get_mcp_tool_dir_path()), "app.tools"),
            (str(get_mcp_prompt_dir_path()), "app.prompts"),
            (str(get_mcp_resource_dir_path()), "app.resources"),
        ],
        load_native_mcp_tools=True,
    )
    return mcp_server


def save_mcp_tools(tool_metadatas: Set[UserMCPToolMetadata]) -> None:
    content_to_save = [asdict(tool) for tool in tool_metadatas]
    content_to_save = sorted(content_to_save, key=lambda x: x["name"])

    output_path = get_mcp_tool_metadata_file_path()
    with open(output_path, "w") as output_file:
        yaml.dump(content_to_save, output_file, sort_keys=True)


def save_mcp_prompts(prompt_metadatas: Set[UserMCPPromptMetadata]) -> None:
    content_to_save = [asdict(prompt_metadata) for prompt_metadata in prompt_metadatas]
    content_to_save = sorted(content_to_save, key=lambda x: x["name"])

    output_path = get_mcp_prompt_metadata_file_path()
    with open(output_path, "w") as output_file:
        yaml.dump(content_to_save, output_file, sort_keys=True)


def save_mcp_resources(resource_metadatas: Set[UserMCPResourceMetadata]) -> None:
    content_to_save = [
        asdict(resource_metadata) for resource_metadata in resource_metadatas
    ]
    content_to_save = sorted(content_to_save, key=lambda x: x["name"])

    output_path = get_mcp_resource_metadata_file_path()
    with open(output_path, "w") as output_file:
        yaml.dump(content_to_save, output_file, sort_keys=True)


async def load_and_save_mcp_tools_metadata(mcp_server: DataRobotMCPServer) -> None:
    mcp_tools = await mcp_server.get_tools()
    save_mcp_tools(
        {UserMCPToolMetadata.from_mcp_tool(mcp_tool) for mcp_tool in mcp_tools.values()}
    )


async def load_and_save_mcp_prompts_metadata(mcp_server: DataRobotMCPServer) -> None:
    mcp_prompts = await mcp_server.get_prompts()
    save_mcp_prompts(
        {
            UserMCPPromptMetadata.from_mcp_prompt(mcp_prompt)
            for mcp_prompt in mcp_prompts.values()
        }
    )


async def load_and_save_mcp_resources_metadata(mcp_server: DataRobotMCPServer) -> None:
    mcp_resources = await mcp_server.get_resources()
    save_mcp_resources(
        {
            UserMCPResourceMetadata.from_mcp_resource(mcp_resource)
            for mcp_resource in mcp_resources.values()
        }
    )
