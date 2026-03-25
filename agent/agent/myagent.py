# Copyright 2025 DataRobot, Inc.
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
from datetime import datetime
from typing import Any, Optional, Union

from datarobot_genai.core.agents import (
    make_system_prompt,
)
from datarobot_genai.langgraph.agent import LangGraphAgent
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_litellm.chat_models import ChatLiteLLM
from langgraph.graph import END, START, MessagesState, StateGraph
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from tensile import TrajectoryLogging

from agent.config import Config


class MyAgent(LangGraphAgent):
    """MyAgent is a custom agent that uses Langgraph to plan and write content.
    It utilizes DataRobot's LLM Gateway or a specific deployment for language model interactions.
    This example illustrates 2 agents that handle content creation tasks, including planning
    and writing blog posts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        verbose: Optional[Union[bool, str]] = True,
        timeout: Optional[int] = 90,
        *,
        llm: Optional[BaseChatModel] = None,
        workflow_tools: Optional[list[BaseTool]] = None,
        **kwargs: Any,
    ):
        """Initializes the MyAgent class with API key, base URL, model, and verbosity settings.

        Args:
            api_key: Optional[str]: API key for authentication with DataRobot services.
                Defaults to None, in which case it will use the DATAROBOT_API_TOKEN environment variable.
            api_base: Optional[str]: Base URL for the DataRobot API.
                Defaults to None, in which case it will use the DATAROBOT_ENDPOINT environment variable.
            model: Optional[str]: The LLM model to use.
                Defaults to None.
            verbose: Optional[Union[bool, str]]: Whether to enable verbose logging.
                Accepts boolean or string values ("true"/"false"). Defaults to True.
            timeout: Optional[int]: How long to wait for the agent to respond.
                Defaults to 90 seconds.
            llm: Optional[BaseChatModel]: Pre-configured LLM instance provided by NAT.
                When set, llm() returns this directly instead of creating a ChatLiteLLM.
            workflow_tools: Optional[list[BaseTool]]: Additional tools from the workflow config (e.g. A2A client tools). Keyword-only.
            **kwargs: Any: Additional keyword arguments passed to the agent.
                Contains any parameters received in the CompletionCreateParams.

        Returns:
            None
        """
        super().__init__(
            api_key=api_key,
            api_base=api_base,
            model=model,
            verbose=verbose,
            timeout=timeout,
            **kwargs,
        )
        self._nat_llm = llm
        self._workflow_tools = workflow_tools or []
        self.config = Config()
        self.default_model = self.config.llm_default_model
        if model in ("unknown", "datarobot-deployed-llm"):
            self.model = self.default_model

        with TrajectoryLogging(trajectory_subdir="myagent"):
            self._http_handler = AsyncHTTPHandler()

    @property
    def workflow(self) -> StateGraph[MessagesState]:
        langgraph_workflow = StateGraph[
            MessagesState, None, MessagesState, MessagesState
        ](MessagesState)
        langgraph_workflow.add_node("planner_node", self.agent_planner)
        langgraph_workflow.add_node("writer_node", self.agent_writer)
        langgraph_workflow.add_edge(START, "planner_node")
        langgraph_workflow.add_edge("planner_node", "writer_node")
        langgraph_workflow.add_edge("writer_node", END)
        return langgraph_workflow  # type: ignore[return-value]

    @property
    def prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful assistant that plans and writes content based on the "
                    "user's topic. Chat history is provided via {chat_history} (it may be empty). "
                    "Use it when helpful to stay consistent across turns.",
                ),
                (
                    "user",
                    f"The topic is {{topic}}. Make sure you find any interesting and "
                    f"relevant information given the current year is {datetime.now().year}.",
                ),
            ]
        )

    def llm(
        self,
        auto_model_override: bool = True,
    ) -> BaseChatModel:
        """Returns the LLM to use for agent nodes.

        In NAT mode, returns the pre-configured LLM provided at construction.
        In DRUM mode, creates a ChatLiteLLM using the configured API credentials.

        Args:
            auto_model_override: Optional[bool]: If True, it will try and use the model
                specified in the request but automatically back out if the LLM Gateway is
                not available.

        Returns:
            BaseChatModel: The model to use.
        """
        if self._nat_llm is not None:
            return self._nat_llm

        api_base = self.litellm_api_base(self.config.llm_deployment_id)
        model = self.model or self.default_model
        if auto_model_override and not self.config.use_datarobot_llm_gateway:
            model = self.default_model
        if self.verbose:
            print(f"Using model: {model}")

        config = {
            "model": model,
            "api_base": api_base,
            "api_key": self.api_key,
            "timeout": self.timeout,
            "streaming": True,
            "max_retries": 3,
        }

        model_kwargs = {"client": self._http_handler}
        if not self.config.use_datarobot_llm_gateway and self._identity_header:
            model_kwargs["extra_headers"] = self._identity_header

        config["model_kwargs"] = model_kwargs  # type: ignore[assignment]

        return ChatLiteLLM(**config)

    @property
    def agent_planner(self) -> Any:
        return create_agent(
            self.llm(),
            tools=self.mcp_tools + self._workflow_tools,
            system_prompt=make_system_prompt(
                "You are a content planner. You create brief, structured outlines for blog articles. "
                "You identify the most important points and cite relevant sources. Keep it simple and to the point - "
                "this is just an outline for the writer.\n"
                "\n"
                "You have access to tools that can help you research and gather information. Use these tools when "
                "required to collect accurate and up-to-date information about the topic for your planning and research.\n"
                "\n"
                "Create a simple outline with:\n"
                "1. 10-15 key points or facts (bullet points only, no paragraphs)\n"
                "2. 2-3 relevant sources or references\n"
                "3. A brief suggested structure (intro, 2-3 sections, conclusion)\n"
                "\n"
                "Do NOT write paragraphs or detailed explanations. Just provide a focused list.",
            ),
            name="planner_agent",
        )

    @property
    def agent_writer(self) -> Any:
        return create_agent(
            self.llm(),
            tools=self.mcp_tools + self._workflow_tools,
            system_prompt=make_system_prompt(
                "You are a content writer working with a planner colleague.\n"
                "You write opinion pieces based on the planner's outline and context. You provide objective and "
                "impartial insights backed by the planner's information. You acknowledge when your statements are "
                "opinions versus objective facts.\n"
                "\n"
                "You have access to tools that can help you verify facts and gather additional supporting information. "
                "Use these tools when required to ensure accuracy and find relevant details while writing.\n"
                "\n"
                "1. Use the content plan to craft a compelling blog post.\n"
                "2. Structure with an engaging introduction, insightful body, and summarizing conclusion.\n"
                "3. Sections/Subtitles are properly named in an engaging manner.\n"
                "4. CRITICAL: Keep the total output under 500 words. Each section should have 1-2 brief paragraphs.\n"
                "\n"
                "Write in markdown format, ready for publication.",
            ),
            name="writer_agent",
        )
