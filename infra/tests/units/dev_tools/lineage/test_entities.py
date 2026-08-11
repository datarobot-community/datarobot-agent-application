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
from dev_tools.lineage.entities import (
    MCPPromptMetadata,
    MCPResourceMetadata,
    MCPToolMetadata,
)
from dev_tools.lineage.enums import (
    DataRobotMCPPromptCategory,
    DataRobotMCPResourceCategory,
    DataRobotMCPToolCategory,
)


class TestMCPToolMetadata:
    def test_from_dict(self) -> None:
        expected_name = "dafa"
        expected_type = "USER_TOOL"
        output = MCPToolMetadata.from_dict(
            {"name": expected_name, "type": expected_type}
        )

        assert output == MCPToolMetadata(
            expected_name, DataRobotMCPToolCategory.from_string(expected_type)
        )


class TestMCPPromptMetadata:
    def test_from_dict(self) -> None:
        expected_name = "dafa"
        expected_type = "USER_PROMPT_TEMPLATE"
        output = MCPPromptMetadata.from_dict(
            {"name": expected_name, "type": expected_type}
        )

        assert output == MCPPromptMetadata(
            expected_name, DataRobotMCPPromptCategory.from_string(expected_type)
        )


class TestMCPResourceMetadata:
    def test_from_dict(self) -> None:
        expected_name = "dafa"
        expected_type = "USER_RESOURCE"
        expected_uri = "adsfdsa"
        output = MCPResourceMetadata.from_dict(
            {"name": expected_name, "type": expected_type, "uri": expected_uri}
        )

        assert output == MCPResourceMetadata(
            expected_name,
            DataRobotMCPResourceCategory.from_string(expected_type),
            expected_uri,
        )
