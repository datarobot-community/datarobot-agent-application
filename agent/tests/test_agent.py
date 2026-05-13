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

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.prompts import ChatPromptTemplate

from agent import MyAgent
from agent.myagent import graph_factory, prompt_template


class TestMyAgentLangGraph:
    @pytest.fixture
    def agent(self) -> MyAgent:
        mock_llm = Mock()
        return MyAgent(llm=mock_llm, verbose=True)

    def test_myagent_is_langgraph_agent_subclass(self):
        """Test that MyAgent inherits from LangGraphAgent."""
        from datarobot_genai.langgraph.agent import LangGraphAgent

        assert issubclass(MyAgent, LangGraphAgent)

    def test_init_with_llm(self):
        """Test initialization with an LLM instance."""
        mock_llm = Mock()
        agent = MyAgent(llm=mock_llm, verbose=True)
        assert agent.llm == mock_llm
        assert agent.verbose is True

    def test_prompt_template_is_chat_prompt(self):
        """Test that prompt_template is a ChatPromptTemplate."""
        assert isinstance(prompt_template, ChatPromptTemplate)

    def test_prompt_template_has_expected_variables(self):
        """Test that prompt_template declares chat_history and topic variables."""
        input_vars = prompt_template.input_variables
        assert "chat_history" in input_vars
        assert "topic" in input_vars

    def test_prompt_template_formats_with_variables(self):
        """Test that prompt_template can be formatted with chat_history and topic."""
        format_kwargs = {
            "chat_history": "User asked about AI trends.",
            "topic": "artificial intelligence",
        }
        messages = prompt_template.format_messages(**format_kwargs)
        assert len(messages) == 2
        assert "{chat_history}" not in messages[0].content
        assert "{topic}" not in messages[1].content
        assert "artificial intelligence" in messages[1].content

    @patch("agent.myagent.create_agent")
    def test_graph_factory_creates_planner_and_writer(self, mock_create_agent):
        """Test that graph_factory creates a graph with planner and writer nodes."""
        mock_llm = Mock()
        mock_tool = Mock()
        graph = graph_factory(mock_llm, [mock_tool], verbose=False)
        assert graph is not None
        assert "planner_node" in graph.nodes
        assert "writer_node" in graph.nodes

    @patch("agent.myagent.create_agent")
    def test_graph_factory_passes_llm_and_tools(self, mock_create_agent):
        """Test that graph_factory passes LLM and tools to agents."""
        mock_llm = Mock()
        mock_tool = Mock()
        graph_factory(mock_llm, [mock_tool], verbose=True)
        assert mock_create_agent.call_count == 2
        for call in mock_create_agent.call_args_list:
            assert call[0][0] == mock_llm
            assert mock_tool in call[1]["tools"]

    def test_workflow_property_uses_graph_factory(self, agent):
        """Test that the agent's workflow property produces a graph."""
        with patch("agent.myagent.create_agent"):
            workflow = agent.workflow
            assert workflow is not None
            assert "planner_node" in workflow.nodes
            assert "writer_node" in workflow.nodes

    @pytest.mark.parametrize(
        "model_value, expected_model_name",
        [
            ("unknown", None),
            ("gpt-4", "gpt-4"),
            ("datarobot-deployed-llm", "datarobot-deployed-llm"),
            (None, None),
        ],
    )
    @patch("agent.myagent.get_llm", return_value=Mock())
    @patch("agent.myagent.agent_chat_completion_wrapper", new_callable=AsyncMock)
    @patch("agent.myagent.mcp_tools_context")
    def test_custompy_adaptor_filters_placeholder_models(
        self,
        mock_mcp_ctx,
        mock_wrapper,
        mock_get_llm,
        model_value,
        expected_model_name,
    ):
        from agent.myagent import custompy_adaptor

        completion_create_params = {
            "model": model_value,
            "messages": [{"role": "user", "content": "hi"}],
        }
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            custompy_adaptor(completion_create_params)
        )
        mock_get_llm.assert_called_once()
        assert mock_get_llm.call_args[1]["model_name"] == expected_model_name
