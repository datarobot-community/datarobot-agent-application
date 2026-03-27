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
from typing import Any, List, Optional, Union

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import BaseTool as CrewAIBaseTool
from datarobot_genai.crewai.agent import CrewAIAgent
from litellm.llms.custom_httpx.http_handler import HTTPHandler

from agent.config import Config


class StopWordLLM(LLM):
    """LLM subclass that enforces stop-word truncation client-side.

    CrewAI sets ``stop=[\"\\nObservation:\"]`` on the LLM so the model stops
    generating before it can hallucinate a tool observation.  That works only
    when the upstream API honours the ``stop`` parameter.  When the request is
    proxied through a gateway that silently drops ``stop`` (or when CrewAI
    itself retries without it after an "Unsupported parameter" error), the
    model produces the entire ``Action → Observation → Final Answer`` chain in
    one completion.  CrewAI's parser then sees ``Final Answer:`` first, returns
    ``AgentFinish``, and the tool call is silently discarded.

    ``BaseLLM._apply_stop_words()`` exists to truncate responses at the first
    stop word, but it is never called by the litellm-based ``LLM.call()``.
    This subclass wires it in so truncation always happens regardless of
    whether the API respected the parameter.
    """

    def call(self, *args: Any, **kwargs: Any) -> Any:
        result = super().call(*args, **kwargs)
        if isinstance(result, str):
            return self._apply_stop_words(result)
        return result


class MyAgent(CrewAIAgent):
    """MyAgent is a custom agent that uses CrewAI to plan and write content.
    It utilizes DataRobot's LLM Gateway or a specific deployment for language model interactions.
    This example illustrates 2 agents that handle content creation tasks, including planning and writing
    blog posts.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        verbose: Optional[Union[bool, str]] = True,
        timeout: Optional[int] = 90,
        *,
        llm: Optional[LLM] = None,
        workflow_tools: Optional[list[CrewAIBaseTool]] = None,
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
            llm: Optional[LLM]: Pre-configured LLM instance provided by NAT.
                When set, llm() returns this directly instead of creating a new LLM.
            workflow_tools: Optional[list[CrewAIBaseTool]]: Additional tools from the workflow config (e.g. A2A client tools). Keyword-only.
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

        self._http_handler = HTTPHandler()

    def llm(
        self,
        auto_model_override: bool = True,
    ) -> LLM:
        """Returns the LLM to use for agent nodes.

        In NAT mode, returns the pre-configured LLM provided at construction.
        In DRUM mode, creates a CrewAI LLM instance using the configured API credentials.

        Args:
            auto_model_override: Optional[bool]: If True, it will try and use the model
                specified in the request but automatically back out if the LLM Gateway is
                not available. Only applies in DRUM mode.

        Returns:
            LLM: The model to use.
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
            "client": self._http_handler,
        }

        if not self.config.use_datarobot_llm_gateway and self._identity_header:
            config["extra_headers"] = self._identity_header  # type: ignore[assignment]

        return StopWordLLM(**config)  # type: ignore[arg-type]

    def make_kickoff_inputs(self, user_prompt_content: str) -> dict[str, Any]:
        """Map the user prompt into Crew kickoff inputs expected by tasks/agents.

        The ``chat_history`` field opts into automatic history injection. When
        prior turns are available the base class populates it with a formatted
        "Prior conversation:\\n..." block; on the first turn it remains an empty
        string. Place ``{chat_history}`` at the end of task descriptions to
        include it as a self-contained section that disappears gracefully when
        there is no history yet.
        """
        return {
            "topic": str(user_prompt_content),
            "chat_history": "",
        }

    @property
    def agents(self) -> List[Agent]:
        return [self.agent_planner, self.agent_writer]

    @property
    def tasks(self) -> List[Task]:
        return [self.task_plan, self.task_write]

    @property
    def agent_planner(self) -> Agent:
        """Content Planner agent."""
        return Agent(
            role="Planner",
            goal="Create a simple, focused outline for {topic} with key points and sources.",
            backstory=(
                "You create brief, structured outlines for blog articles. "
                "You identify the most important points and cite relevant sources. "
                "Keep it simple and to the point - this is just an outline for the writer. "
                "You have access to tools that can help you research and gather information. "
                "Use these tools when required to collect accurate and up-to-date information "
                "about the topic for your planning and research."
            ),
            allow_delegation=False,
            verbose=self.verbose,
            llm=self.llm(),
            tools=self.mcp_tools + self._workflow_tools,
        )

    @property
    def agent_writer(self) -> Agent:
        """Content Writer agent."""
        return Agent(
            role="Writer",
            goal="Write a concise, insightful opinion piece about {topic}. Maximum 500 words.",
            backstory=(
                "You write opinion pieces based on the planner's outline and context. "
                "You provide objective and impartial insights backed by the planner's information. "
                "You acknowledge when your statements are opinions versus objective facts. "
                "You have access to tools that can help you verify facts and gather additional "
                "supporting information. Use these tools when required to ensure accuracy and "
                "find relevant details while writing."
            ),
            allow_delegation=False,
            verbose=self.verbose,
            llm=self.llm(),
            tools=self.mcp_tools + self._workflow_tools,
        )

    @property
    def task_plan(self) -> Task:
        return Task(
            description=(
                "Create a simple outline for {topic} with:\n"
                "1. 10-15 key points or facts (bullet points only, no paragraphs)\n"
                "2. 2-3 relevant sources or references\n"
                "3. A brief suggested structure (intro, 2-3 sections, conclusion)\n"
                "Do NOT write paragraphs or detailed explanations. Just provide a focused list.\n"
                "{chat_history}"
            ),
            expected_output="A simple outline with 10-15 bullet points, 2-3 sources, and a basic structure. "
            "No paragraphs or lengthy explanations.",
            agent=self.agent_planner,
        )

    @property
    def task_write(self) -> Task:
        return Task(
            description=(
                "1. Use the content plan to craft a compelling blog post on {topic}.\n"
                "2. Structure with an engaging introduction, insightful body, and summarizing conclusion.\n"
                "3. Sections/Subtitles are properly named in an engaging manner.\n"
                "4. CRITICAL: Keep the total output under 500 words. Each section should have 1-2 brief paragraphs.\n"
                "{chat_history}"
            ),
            expected_output="A well-written blog post in markdown format, ready for publication. Maximum 500 words total.",
            agent=self.agent_writer,
        )

    def crew(self) -> Crew:
        """Create a CrewAI workflow instance.

        Default implementation in base class `CrewAIAgent` constructs a Crew with provided agents and tasks.
        Here you can override to customize Crew options.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            verbose=self.verbose,
            process=Process.sequential,
        )
