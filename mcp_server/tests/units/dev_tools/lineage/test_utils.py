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
from dataclasses import asdict
from typing import Iterator
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from fastmcp.prompts import Prompt
from fastmcp.resources import Resource
from fastmcp.tools import Tool

from dev_tools.lineage.entities import (
    UserMCPPromptMetadata,
    UserMCPResourceMetadata,
    UserMCPToolMetadata,
)
from dev_tools.lineage.utils import (
    get_dr_mcp_server_instance,
    get_mcp_item_metadata_dir_path,
    get_mcp_prompt_dir_path,
    get_mcp_resource_dir_path,
    get_mcp_tool_dir_path,
    load_and_save_mcp_prompts_metadata,
    load_and_save_mcp_resources_metadata,
    load_and_save_mcp_tools_metadata,
    save_mcp_prompts,
    save_mcp_resources,
    save_mcp_tools,
)


class TestLineageUtils:
    @pytest.fixture
    def module_under_testing(self) -> str:
        return "dev_tools.lineage.utils"

    @pytest.fixture
    def mock_mcp(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.mcp") as mock_mcp:
            yield mock_mcp

    @pytest.fixture
    def mock_dr_mcp_server_cls(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.DataRobotMCPServer") as mock_mcp_cls:
            yield mock_mcp_cls

    @pytest.fixture
    def mock_get_mcp_tool_dir_path(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.get_mcp_tool_dir_path") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_mcp_prompt_dir_path(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.get_mcp_prompt_dir_path") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_mcp_resource_dir_path(
        self, module_under_testing: str
    ) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.get_mcp_resource_dir_path") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_dr_mcp_server_instance(
        self,
        module_under_testing: str,
    ) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.get_dr_mcp_server_instance") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_save_mcp_tools(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.save_mcp_tools") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_save_mcp_prompts(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.save_mcp_prompts") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_save_mcp_resources(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.save_mcp_resources") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_mcp_tool_metadata_file_path(
        self, module_under_testing: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_testing}.get_mcp_tool_metadata_file_path"
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_mcp_resource_metadata_file_path(
        self, module_under_testing: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_testing}.get_mcp_resource_metadata_file_path"
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_mcp_prompt_metadata_file_path(
        self, module_under_testing: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_testing}.get_mcp_prompt_metadata_file_path"
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_open_context_manager(self, module_under_testing: str) -> Iterator[Mock]:
        with patch(f"{module_under_testing}.open") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_yaml_dump(self) -> Iterator[Mock]:
        with patch.object(yaml, "dump") as mock_func:
            yield mock_func

    def test_mcp_tool_dir_path_exits(self) -> None:
        assert get_mcp_tool_dir_path().exists()

    def test_get_mcp_prompt_dir_path_exists(self) -> None:
        assert get_mcp_prompt_dir_path().exists()

    def test_get_mcp_resource_dir_path_exists(self) -> None:
        assert get_mcp_resource_dir_path().exists()

    def test_get_mcp_item_config_dir_path_exists(self) -> None:
        assert get_mcp_item_metadata_dir_path().exists()

    @pytest.mark.asyncio
    def test_get_dr_mcp_server_instance(
        self,
        mock_dr_mcp_server_cls: Mock,
        mock_get_mcp_prompt_dir_path: Mock,
        mock_get_mcp_resource_dir_path: Mock,
        mock_get_mcp_tool_dir_path: Mock,
        mock_mcp: Mock,
    ) -> None:
        dr_mcp_server = get_dr_mcp_server_instance()

        mock_dr_mcp_server_cls.assert_called_once_with(
            mock_mcp,
            additional_module_paths=[
                (str(mock_get_mcp_tool_dir_path.return_value), "app.tools"),
                (str(mock_get_mcp_prompt_dir_path.return_value), "app.prompts"),
                (str(mock_get_mcp_resource_dir_path.return_value), "app.resources"),
            ],
            load_native_mcp_tools=True,
        )
        assert dr_mcp_server == mock_dr_mcp_server_cls.return_value

    def test_save_mcp_tools(
        self,
        mock_get_mcp_tool_metadata_file_path: Mock,
        mock_open_context_manager: Mock,
        mock_yaml_dump: Mock,
    ) -> None:
        tool_one = UserMCPToolMetadata(name="bbb", type="dafad")
        tool_two = UserMCPToolMetadata(name="aaa", type="dafad")
        mcp_tools = {tool_one, tool_two}
        save_mcp_tools(mcp_tools)

        mock_open_context_manager.assert_called_once_with(
            mock_get_mcp_tool_metadata_file_path.return_value,
            "w",
        )
        mock_output_file = mock_open_context_manager.return_value.__enter__.return_value
        mock_yaml_dump.assert_called_once_with(
            [asdict(tool_two), asdict(tool_one)],
            mock_output_file,
            sort_keys=True,
        )

    def test_save_mcp_prompts(
        self,
        mock_get_mcp_prompt_metadata_file_path: Mock,
        mock_open_context_manager: Mock,
        mock_yaml_dump: Mock,
    ) -> None:
        prompt_one = UserMCPPromptMetadata(name="bbb", type="dafad")
        prompt_two = UserMCPPromptMetadata(name="aaa", type="dafad")
        mcp_prompts = {prompt_one, prompt_two}
        save_mcp_prompts(mcp_prompts)

        mock_open_context_manager.assert_called_once_with(
            mock_get_mcp_prompt_metadata_file_path.return_value,
            "w",
        )
        mock_output_file = mock_open_context_manager.return_value.__enter__.return_value
        mock_yaml_dump.assert_called_once_with(
            [asdict(prompt_two), asdict(prompt_one)],
            mock_output_file,
            sort_keys=True,
        )

    def test_save_mcp_resources(
        self,
        mock_get_mcp_resource_metadata_file_path: Mock,
        mock_open_context_manager: Mock,
        mock_yaml_dump: Mock,
    ) -> None:
        resource_one = UserMCPResourceMetadata(
            name="bbb", type="dafad", uri="uri://bbb"
        )
        resource_two = UserMCPResourceMetadata(
            name="aaa", type="dafad", uri="uri://aaa"
        )
        mcp_resources = {resource_one, resource_two}
        save_mcp_resources(mcp_resources)

        mock_open_context_manager.assert_called_once_with(
            mock_get_mcp_resource_metadata_file_path.return_value,
            "w",
        )
        mock_output_file = mock_open_context_manager.return_value.__enter__.return_value
        mock_yaml_dump.assert_called_once_with(
            [asdict(resource_two), asdict(resource_one)],
            mock_output_file,
            sort_keys=True,
        )

    @pytest.mark.asyncio
    async def test_read_and_save_mcp_tools(
        self,
        mock_save_mcp_tools: Mock,
    ) -> None:
        mcp_server = Mock()
        tool_name = "bbb"
        tool_type = "adfas"
        mcp_tool = Tool(
            name=tool_name, meta={"tool_category": tool_type}, parameters={}
        )
        mcp_server.get_tools = AsyncMock(return_value={"sadfa": mcp_tool})

        await load_and_save_mcp_tools_metadata(mcp_server)

        mcp_server.get_tools.assert_called_once_with()
        (mcp_tool_metadatas,) = mock_save_mcp_tools.call_args.args
        assert len(mcp_tool_metadatas) == 1
        mcp_tool_metadata = mcp_tool_metadatas.pop()
        assert mcp_tool_metadata.name == tool_name
        assert mcp_tool_metadata.type == tool_type

    @pytest.mark.asyncio
    async def test_read_and_save_mcp_prompts(
        self,
        mock_save_mcp_prompts: Mock,
    ) -> None:
        mcp_server = Mock()
        prompt_name = "bbb"
        prompt_type = "adfad"
        mcp_prompt = Prompt(name=prompt_name, meta={"prompt_category": prompt_type})
        mcp_server.get_prompts = AsyncMock(return_value={"sadfa": mcp_prompt})

        await load_and_save_mcp_prompts_metadata(mcp_server)

        mcp_server.get_prompts.assert_called_once_with()
        (mcp_prompt_metadatas,) = mock_save_mcp_prompts.call_args.args
        assert len(mcp_prompt_metadatas) == 1
        mcp_prompt_metadata = mcp_prompt_metadatas.pop()
        assert mcp_prompt_metadata.name == prompt_name
        assert mcp_prompt_metadata.type == prompt_type

    @pytest.mark.asyncio
    async def test_read_and_save_mcp_resources(
        self,
        mock_save_mcp_resources: Mock,
    ) -> None:
        mcp_server = Mock()
        resource_name = "bbb"
        resource_type = "adfad"
        resource_uri = "uri://bbb"
        mcp_resource = Resource(
            name=resource_name,
            meta={"resource_category": resource_type},
            uri=resource_uri,
        )
        mcp_server.get_resources = AsyncMock(return_value={"sadfa": mcp_resource})

        await load_and_save_mcp_resources_metadata(mcp_server)

        mcp_server.get_resources.assert_called_once_with()
        (mcp_resource_metadatas,) = mock_save_mcp_resources.call_args.args
        assert len(mcp_resource_metadatas) == 1
        mcp_resource_metadata = mcp_resource_metadatas.pop()
        assert mcp_resource_metadata.name == resource_name
        assert mcp_resource_metadata.type == resource_type
        assert mcp_resource_metadata.uri == resource_uri
