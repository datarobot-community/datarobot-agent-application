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
import pytest

from dev_tools.lineage.enums import (
    DataRobotMCPPromptCategory,
    DataRobotMCPResourceCategory,
    DataRobotMCPToolCategory,
)


class TestDataRobotMCPToolCategory:
    @pytest.mark.parametrize(
        "tool_category", [tool_category for tool_category in DataRobotMCPToolCategory]
    )
    def test_from_string(self, tool_category: DataRobotMCPToolCategory) -> None:
        assert DataRobotMCPToolCategory.from_string(tool_category.name) == tool_category


class TestDataRobotMCPPromptCategory:
    @pytest.mark.parametrize(
        "prompt_category",
        [prompt_category for prompt_category in DataRobotMCPPromptCategory],
    )
    def test_from_string(self, prompt_category: DataRobotMCPPromptCategory) -> None:
        assert (
            DataRobotMCPPromptCategory.from_string(prompt_category.name)
            == prompt_category
        )


class TestDataRobotMCPResourceCategory:
    @pytest.mark.parametrize(
        "resource_category",
        [resource_category for resource_category in DataRobotMCPResourceCategory],
    )
    def test_from_string(self, resource_category: DataRobotMCPResourceCategory) -> None:
        assert (
            DataRobotMCPResourceCategory.from_string(resource_category.name)
            == resource_category
        )
