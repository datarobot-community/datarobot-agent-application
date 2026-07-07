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

"""
Tests for MCP LangGraph integration - verifying the register.py agent function
loads MCP tools and injects them into the agent.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from datarobot_genai.core.mcp import MCPConfig

from agent.register import LanggraphAgentConfig, langgraph_agent


@pytest.fixture
def mock_builder():
    """A NAT builder stub that returns a mock LLM and a single workflow tool."""
    builder = MagicMock()
    builder.get_llm = AsyncMock(return_value=MagicMock())
    builder.get_tools = AsyncMock(return_value=[MagicMock(name="workflow_tool")])
    return builder


@pytest.fixture
def agent_config():
    return LanggraphAgentConfig(llm_name="datarobot_llm", description="Test agent")


class TestMCPIntegration:
    """Test MCP tool integration for LangGraph agents via the register.py agent function."""

    async def test_agent_function_injects_mcp_tools(
        self, mock_builder, agent_config, mock_agent_response, monkeypatch
    ):
        """The agent function loads MCP tools and passes them to MyAgent alongside workflow tools."""
        mcp_tool = MagicMock(name="mcp_tool")
        captured: dict[str, MCPConfig] = {}

        @asynccontextmanager
        async def fake_mcp_tools_context(mcp_config):
            captured["mcp_config"] = mcp_config
            yield [mcp_tool]

        mock_agent_instance = MagicMock()
        mock_agent_instance.invoke = Mock(return_value=mock_agent_response)
        mock_agent_class = MagicMock(return_value=mock_agent_instance)

        monkeypatch.setattr(
            "datarobot_genai.langgraph.mcp.mcp_tools_context", fake_mcp_tools_context
        )
        monkeypatch.setattr("agent.myagent.MyAgent", mock_agent_class)

        async with langgraph_agent(agent_config, mock_builder) as func_info:
            async for _ in func_info.stream_fn(MagicMock()):
                pass

        # MCP tools were loaded with a request-scoped MCPConfig ...
        assert isinstance(captured["mcp_config"], MCPConfig)
        # ... and injected into the agent alongside the workflow tools.
        mock_agent_class.assert_called_once()
        tools = mock_agent_class.call_args.kwargs["tools"]
        assert mcp_tool in tools
        assert len(tools) == 2
