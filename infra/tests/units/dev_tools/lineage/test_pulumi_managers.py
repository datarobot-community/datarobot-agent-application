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
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pulumi
import pytest
import yaml  # type: ignore[import-untyped]

from dev_tools.lineage.entities import (
    MCPPromptMetadata,
    MCPResourceMetadata,
    MCPToolMetadata,
)
from dev_tools.lineage.pulumi_managers import (
    MCPPromptMetadataPulumiManager,
    MCPResourceMetadataPulumiManager,
    MCPToolMetadataPulumiManager,
    get_mcp_item_metadata_dir_path,
    get_mcp_prompt_metadata_file_path,
    get_mcp_resource_metadata_file_path,
    get_mcp_tool_metadata_file_path,
    load_from_yaml,
)


@pytest.fixture
def module_under_test() -> str:
    return "dev_tools.lineage.pulumi_managers"


@pytest.fixture
def mock_load_from_yaml(module_under_test: str) -> Iterator[Mock]:
    with patch(f"{module_under_test}.load_from_yaml") as mock_func:
        yield mock_func


@pytest.fixture
def mock_pulumi_export() -> Iterator[Mock]:
    with patch.object(pulumi, "export") as mock_func:
        yield mock_func


class TestMCPMetadataPaths:
    @pytest.fixture
    def mock_mcp_item_metadata_dir_path(self) -> Path:
        return Path("dafda")

    @pytest.fixture
    def mock_get_mcp_item_metadata_dir_path(
        self,
        mock_mcp_item_metadata_dir_path: Path,
        module_under_test: str,
    ) -> Iterator[Mock]:
        with patch(f"{module_under_test}.get_mcp_item_metadata_dir_path") as mock_func:
            mock_func.return_value = mock_mcp_item_metadata_dir_path
            yield mock_func

    def test_get_mcp_tool_metadata_config_path(self) -> None:
        assert get_mcp_item_metadata_dir_path().exists()

    @pytest.mark.usefixtures("mock_get_mcp_item_metadata_dir_path")
    def test_get_mcp_tool_metadata_file_path(
        self,
        mock_mcp_item_metadata_dir_path: Path,
    ) -> None:
        assert (
            get_mcp_tool_metadata_file_path()
            == mock_mcp_item_metadata_dir_path / "mcp_tools.yaml"
        )

    @pytest.mark.usefixtures("mock_get_mcp_item_metadata_dir_path")
    def test_get_mcp_prompt_metadata_file_path(
        self,
        mock_mcp_item_metadata_dir_path: Path,
    ) -> None:
        assert (
            get_mcp_prompt_metadata_file_path()
            == mock_mcp_item_metadata_dir_path / "mcp_prompts.yaml"
        )

    @pytest.mark.usefixtures("mock_get_mcp_item_metadata_dir_path")
    def test_get_mcp_resource_metadata_file_path(
        self,
        mock_mcp_item_metadata_dir_path: Path,
    ) -> None:
        assert (
            get_mcp_resource_metadata_file_path()
            == mock_mcp_item_metadata_dir_path / "mcp_resources.yaml"
        )


class TestLoadYAML:
    @pytest.fixture
    def mock_open_context_manager(self, module_under_test: str) -> Iterator[Mock]:
        with patch(f"{module_under_test}.open") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_yaml_safe_load(self) -> Iterator[Mock]:
        with patch.object(yaml, "safe_load") as mock_func:
            yield mock_func

    def test_load_from_yaml(
        self,
        mock_open_context_manager: Mock,
        mock_yaml_safe_load: Mock,
    ) -> None:
        yaml_path = Mock()
        load_from_yaml(yaml_path)

        mock_open_context_manager.assert_called_once_with(yaml_path, "r")
        mock_input_file = mock_open_context_manager.return_value.__enter__.return_value
        mock_yaml_safe_load.assert_called_once_with(mock_input_file)


class TestMCPToolMetadataPulumiManager:
    @pytest.fixture
    def mock_get_mcp_tool_metadata_file_path(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(f"{module_under_test}.get_mcp_tool_metadata_file_path") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_mcp_tool_metadata_from_dict(self) -> Iterator[Mock]:
        with patch.object(MCPToolMetadata, "from_dict") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_pulumi_resource_name(self) -> Iterator[Mock]:
        with patch.object(
            MCPToolMetadataPulumiManager,
            "get_pulumi_resource_name",
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_pulumi_resource_cls(self, module_under_test: str) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.UserMcpToolMetadataPulumiResource"
        ) as mock_cls:
            yield mock_cls

    @pytest.fixture
    def mock_pulumi_resource_creation_output_cls(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.MCPToolMetadataPulumiResourceCreateOutput"
        ) as mock_cls:
            yield mock_cls

    def test_init(self, mock_get_mcp_tool_metadata_file_path: Mock) -> None:
        pulumi_manager = MCPToolMetadataPulumiManager()

        mock_get_mcp_tool_metadata_file_path.assert_called_once_with()
        assert (
            pulumi_manager.metadata_file_path
            == mock_get_mcp_tool_metadata_file_path.return_value
        )

    def test_load_metadata(
        self,
        mock_mcp_tool_metadata_from_dict: Mock,
        mock_load_from_yaml: Mock,
    ) -> None:
        loaded_metadata = Mock()
        mock_load_from_yaml.return_value = [loaded_metadata]

        pulumi_manager = MCPToolMetadataPulumiManager()
        outputs = pulumi_manager.load_metadata()

        mock_load_from_yaml.assert_called_once_with(pulumi_manager.metadata_file_path)
        mock_mcp_tool_metadata_from_dict.assert_called_once_with(loaded_metadata)
        assert outputs == {mock_mcp_tool_metadata_from_dict.return_value}

    def test_create_pulumi_resources(
        self,
        mock_get_pulumi_resource_name: Mock,
        mock_pulumi_resource_cls: Mock,
        mock_pulumi_resource_creation_output_cls: Mock,
    ) -> None:
        pulumi_manager = MCPToolMetadataPulumiManager()
        metadata_entity = Mock()
        resource_name_prefix = Mock()
        mcp_server_version_id = Mock()
        outputs = pulumi_manager.create_pulumi_resources(
            {metadata_entity},
            resource_name_prefix,
            mcp_server_version_id,
        )

        mock_get_pulumi_resource_name.assert_called_once_with(
            metadata_entity.name,
            resource_name_prefix,
        )
        mock_pulumi_resource_cls.assert_called_once_with(
            resource_name=mock_get_pulumi_resource_name.return_value,
            name=metadata_entity.name,
            type=metadata_entity.type.to_api_representation.return_value,
            mcp_server_version_id=mcp_server_version_id,
        )
        mock_pulumi_resource_creation_output_cls.assert_called_once_with(
            name=mock_get_pulumi_resource_name.return_value,
            pulumi_resource=mock_pulumi_resource_cls.return_value,
        )
        assert outputs == {mock_pulumi_resource_creation_output_cls.return_value}

    def test_export_to_pulumi_stack(
        self,
        mock_pulumi_export: Mock,
    ) -> None:
        pulumi_resource_creation_output = Mock()
        MCPToolMetadataPulumiManager.export_to_pulumi_stack(
            {pulumi_resource_creation_output}
        )

        mock_pulumi_export.assert_called_once_with(
            pulumi_resource_creation_output.name,
            pulumi_resource_creation_output.pulumi_resource.id,
        )


class TestMCPPromptMetadataPulumiManager:
    @pytest.fixture
    def mock_get_mcp_prompt_metadata_file_path(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.get_mcp_prompt_metadata_file_path"
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_mcp_prompt_metadata_from_dict(self) -> Iterator[Mock]:
        with patch.object(MCPPromptMetadata, "from_dict") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_pulumi_resource_name(self) -> Iterator[Mock]:
        with patch.object(
            MCPPromptMetadataPulumiManager,
            "get_pulumi_resource_name",
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_pulumi_resource_cls(self, module_under_test: str) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.UserMcpPromptMetadataPulumiResource"
        ) as mock_cls:
            yield mock_cls

    @pytest.fixture
    def mock_pulumi_resource_creation_output_cls(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.MCPPromptMetadataPulumiResourceCreateOutput"
        ) as mock_cls:
            yield mock_cls

    def test_init(self, mock_get_mcp_prompt_metadata_file_path: Mock) -> None:
        pulumi_manager = MCPPromptMetadataPulumiManager()

        mock_get_mcp_prompt_metadata_file_path.assert_called_once_with()
        assert (
            pulumi_manager.metadata_file_path
            == mock_get_mcp_prompt_metadata_file_path.return_value
        )

    def test_load_metadata(
        self,
        mock_mcp_prompt_metadata_from_dict: Mock,
        mock_load_from_yaml: Mock,
    ) -> None:
        loaded_metadata = Mock()
        mock_load_from_yaml.return_value = [loaded_metadata]

        pulumi_manager = MCPPromptMetadataPulumiManager()
        outputs = pulumi_manager.load_metadata()

        mock_load_from_yaml.assert_called_once_with(pulumi_manager.metadata_file_path)
        mock_mcp_prompt_metadata_from_dict.assert_called_once_with(loaded_metadata)
        assert outputs == {mock_mcp_prompt_metadata_from_dict.return_value}

    def test_create_pulumi_resources(
        self,
        mock_get_pulumi_resource_name: Mock,
        mock_pulumi_resource_cls: Mock,
        mock_pulumi_resource_creation_output_cls: Mock,
    ) -> None:
        pulumi_manager = MCPPromptMetadataPulumiManager()
        metadata_entity = Mock()
        resource_name_prefix = Mock()
        mcp_server_version_id = Mock()
        outputs = pulumi_manager.create_pulumi_resources(
            {metadata_entity},
            resource_name_prefix,
            mcp_server_version_id,
        )

        mock_get_pulumi_resource_name.assert_called_once_with(
            metadata_entity.name,
            resource_name_prefix,
        )
        mock_pulumi_resource_cls.assert_called_once_with(
            resource_name=mock_get_pulumi_resource_name.return_value,
            name=metadata_entity.name,
            type=metadata_entity.type.to_api_representation.return_value,
            mcp_server_version_id=mcp_server_version_id,
        )
        mock_pulumi_resource_creation_output_cls.assert_called_once_with(
            name=mock_get_pulumi_resource_name.return_value,
            pulumi_resource=mock_pulumi_resource_cls.return_value,
        )
        assert outputs == {mock_pulumi_resource_creation_output_cls.return_value}

    def test_export_to_pulumi_stack(
        self,
        mock_pulumi_export: Mock,
    ) -> None:
        pulumi_resource_creation_output = Mock()
        MCPPromptMetadataPulumiManager.export_to_pulumi_stack(
            {pulumi_resource_creation_output}
        )

        mock_pulumi_export.assert_called_once_with(
            pulumi_resource_creation_output.name,
            pulumi_resource_creation_output.pulumi_resource.id,
        )


class TestMCPResourceMetadataPulumiManager:
    @pytest.fixture
    def mock_get_mcp_resource_metadata_file_path(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.get_mcp_resource_metadata_file_path"
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_mcp_resource_metadata_from_dict(self) -> Iterator[Mock]:
        with patch.object(MCPResourceMetadata, "from_dict") as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_get_pulumi_resource_name(self) -> Iterator[Mock]:
        with patch.object(
            MCPResourceMetadataPulumiManager,
            "get_pulumi_resource_name",
        ) as mock_func:
            yield mock_func

    @pytest.fixture
    def mock_pulumi_resource_cls(self, module_under_test: str) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.UserMcpResourceMetadataPulumiResource"
        ) as mock_cls:
            yield mock_cls

    @pytest.fixture
    def mock_pulumi_resource_creation_output_cls(
        self, module_under_test: str
    ) -> Iterator[Mock]:
        with patch(
            f"{module_under_test}.MCPResourceMetadataPulumiResourceCreateOutput"
        ) as mock_cls:
            yield mock_cls

    def test_init(self, mock_get_mcp_resource_metadata_file_path: Mock) -> None:
        pulumi_manager = MCPResourceMetadataPulumiManager()

        mock_get_mcp_resource_metadata_file_path.assert_called_once_with()
        assert (
            pulumi_manager.metadata_file_path
            == mock_get_mcp_resource_metadata_file_path.return_value
        )

    def test_load_metadata(
        self,
        mock_mcp_resource_metadata_from_dict: Mock,
        mock_load_from_yaml: Mock,
    ) -> None:
        loaded_metadata = Mock()
        mock_load_from_yaml.return_value = [loaded_metadata]

        pulumi_manager = MCPResourceMetadataPulumiManager()
        outputs = pulumi_manager.load_metadata()

        mock_load_from_yaml.assert_called_once_with(pulumi_manager.metadata_file_path)
        mock_mcp_resource_metadata_from_dict.assert_called_once_with(loaded_metadata)
        assert outputs == {mock_mcp_resource_metadata_from_dict.return_value}

    def test_create_pulumi_resources(
        self,
        mock_get_pulumi_resource_name: Mock,
        mock_pulumi_resource_cls: Mock,
        mock_pulumi_resource_creation_output_cls: Mock,
    ) -> None:
        pulumi_manager = MCPResourceMetadataPulumiManager()
        metadata_entity = Mock()
        resource_name_prefix = Mock()
        mcp_server_version_id = Mock()
        outputs = pulumi_manager.create_pulumi_resources(
            {metadata_entity},
            resource_name_prefix,
            mcp_server_version_id,
        )

        mock_get_pulumi_resource_name.assert_called_once_with(
            metadata_entity.name,
            resource_name_prefix,
        )
        mock_pulumi_resource_cls.assert_called_once_with(
            resource_name=mock_get_pulumi_resource_name.return_value,
            name=metadata_entity.name,
            type=metadata_entity.type.to_api_representation.return_value,
            uri=metadata_entity.uri,
            mcp_server_version_id=mcp_server_version_id,
        )
        mock_pulumi_resource_creation_output_cls.assert_called_once_with(
            name=mock_get_pulumi_resource_name.return_value,
            pulumi_resource=mock_pulumi_resource_cls.return_value,
        )
        assert outputs == {mock_pulumi_resource_creation_output_cls.return_value}

    def test_export_to_pulumi_stack(
        self,
        mock_pulumi_export: Mock,
    ) -> None:
        pulumi_resource_creation_output = Mock()
        MCPResourceMetadataPulumiManager.export_to_pulumi_stack(
            {pulumi_resource_creation_output}
        )

        mock_pulumi_export.assert_called_once_with(
            pulumi_resource_creation_output.name,
            pulumi_resource_creation_output.pulumi_resource.id,
        )
