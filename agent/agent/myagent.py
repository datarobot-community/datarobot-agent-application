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

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Union, cast

from datarobot_genai.langgraph.agent import LangGraphAgent
from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_litellm.chat_models import ChatLiteLLM
from langgraph.graph import MessagesState, StateGraph

from agent.config import Config

# ── Upstream bug-fix: missing session.initialize() in mcp_tools_context ───────
# datarobot_genai.langgraph.mcp.mcp_tools_context calls load_mcp_tools(session=)
# without first calling session.initialize().  Lenient servers (local MCP) ignore
# this; strict servers (NemoClaw staging) return HTTP 400 on the first request
# because no session has been established.  This patch adds the missing call.
# TODO: remove once datarobot_genai ships the fix upstream.
import datarobot_genai.langgraph.agent as _dr_agent
import datarobot_genai.langgraph.mcp as _dr_mcp
from datarobot_genai.core.mcp.common import MCPConfig
from langchain_mcp_adapters.sessions import (
    SSEConnection,
    StreamableHttpConnection,
    create_session,
)
from langchain_mcp_adapters.tools import load_mcp_tools as _load_mcp_tools


@asynccontextmanager
async def _mcp_tools_context_patched(
    authorization_context: dict[str, Any] | None = None,
    forwarded_headers: dict[str, str] | None = None,
) -> AsyncGenerator[list[BaseTool], None]:
    mcp_config = MCPConfig(
        authorization_context=authorization_context,
        forwarded_headers=forwarded_headers,
    )
    server_config = mcp_config.server_config

    if not server_config:
        print("No MCP server configured, using empty tools list", flush=True)
        yield []
        return

    url = server_config["url"]
    print(f"Connecting to MCP server: {url}", flush=True)

    transport = server_config.pop("transport", "streamable-http")

    if transport in ["streamable-http", "streamable_http"]:
        connection = StreamableHttpConnection(transport="streamable_http", **server_config)
    elif transport == "sse":
        connection = SSEConnection(transport="sse", **server_config)
    else:
        raise RuntimeError("Unsupported MCP transport specified.")

    async with create_session(connection=connection) as session:
        await session.initialize()
        raw_tools = await _load_mcp_tools(session=session)
        tools = [_dr_mcp._wrap_mcp_tool_for_langgraph(t) for t in raw_tools]
        print(f"Successfully loaded {len(tools)} MCP tools", flush=True)
        yield tools


_dr_mcp.mcp_tools_context = _mcp_tools_context_patched
_dr_agent.mcp_tools_context = _mcp_tools_context_patched
# ─────────────────────────────────────────────────────────────────────────────

# souls/ lives at the repo root — two levels above agent/agent/
SOULS_DIR = Path(__file__).parents[2] / "souls"
DEFAULT_SOUL = "supply-chain"


def _load_active_soul() -> tuple[str, str, list[str]]:
    """Read active soul name, system prompt, and allowed tool names.

    Returns
    -------
    tuple[str, str, list[str]]
        (soul_name, system_prompt_text, list_of_allowed_tool_names)
    """
    active_file = SOULS_DIR / ".active"
    name = active_file.read_text().strip() if active_file.exists() else DEFAULT_SOUL

    soul_dir = SOULS_DIR / name
    prompt_file = soul_dir / "SOUL.md"
    tools_file = soul_dir / "mcp-tools.json"

    prompt = prompt_file.read_text() if prompt_file.exists() else ""
    tools: list[str] = (
        json.loads(tools_file.read_text()).get("tools", [])
        if tools_file.exists()
        else []
    )

    return name, prompt, tools


class MyAgent(LangGraphAgent):
    """Soul-driven agent runtime.

    On every invocation the agent reads souls/.active, loads the corresponding
    SOUL.md as its system prompt, and filters self.mcp_tools to only the tools
    declared in mcp-tools.json for that soul.

    To swap domains: write a different soul name to souls/.active (or call
    POST /api/v1/soul/swap/{name}). The next request will pick it up with no
    restart required.

    To edit a soul: modify souls/<name>/SOUL.md. Changes take effect on the
    next request.

    To add tools: add the tool name to souls/<name>/mcp-tools.json. The tool
    must exist on the connected MCP server.
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

    @property
    def workflow(self) -> StateGraph[MessagesState]:  # type: ignore[override]
        # Re-read soul on every invocation — soul is editable, pack is swappable,
        # agent rebuilds itself fresh each time.
        soul_name, soul_prompt, soul_tool_names = _load_active_soul()

        soul_tool_set = set(soul_tool_names)
        filtered_tools = [t for t in self.mcp_tools if t.name in soul_tool_set]
        all_tools = filtered_tools + self._workflow_tools

        if self.verbose:
            loaded = [t.name for t in filtered_tools]
            print(f"[SOUL] Active: {soul_name}", flush=True)
            print(f"[SOUL] Tools ({len(loaded)}): {loaded}", flush=True)

        # create_deep_agent returns a CompiledStateGraph — already compiled.
        # Built-in: write_todos, virtual filesystem, task (sub-agents),
        # SummarizationMiddleware (context compaction).
        return create_deep_agent(  # type: ignore[return-value]
            model=self.llm(),
            tools=all_tools,
            system_prompt=soul_prompt,
            name="soul_agent",
        )

    async def _invoke(self, run_agent_input: Any) -> Any:
        # Override parent's _invoke to skip .compile() — create_deep_agent
        # returns a CompiledStateGraph which has no .compile() method.
        graph = self.workflow
        input_command = self.convert_input_message(run_agent_input)
        # Command.update contains {"messages": [...]}; deepagents expects a dict.
        graph_stream = cast(
            AsyncGenerator[tuple[Any, str, Any], None],
            graph.astream(
                input=input_command.update,
                config=cast(Any, self.langgraph_config),
                debug=self.verbose,
                stream_mode=["updates", "messages"],
                subgraphs=True,
            ),
        )
        usage_metrics: dict[str, int] = {
            "completion_tokens": 0,
            "prompt_tokens": 0,
            "total_tokens": 0,
        }
        return self._stream_generator(graph_stream, usage_metrics, run_agent_input)

    @property
    def prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("user", "{user_prompt_content}"),
        ])

    def llm(
        self,
        auto_model_override: bool = True,
    ) -> BaseChatModel:
        """Returns the LLM to use for agent nodes.

        In NAT mode, returns the pre-configured LLM provided at construction.
        In DRUM mode, creates a ChatLiteLLM using the configured API credentials.
        """
        if self._nat_llm is not None:
            return self._nat_llm

        if self.config.use_datarobot_llm_gateway:
            from urllib.parse import urlparse
            parsed = urlparse(self.api_base)
            base = f"{parsed.scheme}://{parsed.netloc}"
            api_base = f"{base}/api/v2/genai/llmgw"
            gateway_model = self.model or self.default_model
            model = f"openai/{gateway_model}"
        else:
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

        if not self.config.use_datarobot_llm_gateway and self._identity_header:
            config["model_kwargs"] = {"extra_headers": self._identity_header}  # type: ignore[assignment]

        return ChatLiteLLM(**config)
