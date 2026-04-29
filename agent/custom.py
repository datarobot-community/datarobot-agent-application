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
# ------------------------------------------------------------------------------
# THIS SECTION OF CODE IS REQUIRED TO SETUP TRACING AND TELEMETRY FOR THE AGENTS.
# REMOVING THIS CODE WILL DISABLE ALL MONITORING, TRACING AND TELEMETRY.
# isort: off
import os

from datarobot_genai.core.telemetry_agent import instrument

# `opentelemetry-instrumentation-langchain` wraps `Pregel.astream` and detaches context in a
# `finally` after `yield`. If the stream is closed early (GeneratorExit) or the async
# generator is torn down across task/thread boundaries, OpenTelemetry can log:
#   ValueError: ... was created in a different Context
#   Failed to detach context
# This is a known rough edge; LangGraph span wiring is optional. Set to 1 in dev to
# keep HTTP/LLM instrumentation but skip the langchain package's LangGraph wrapper.
if os.environ.get("DR_AGENT_DISABLE_LANGGRAPH_OTEL", "").lower() in (
    "1",
    "true",
    "yes",
):
    instrument()
else:
    instrument(framework="langgraph")
# ruff: noqa: E402
from agent import Config, custompy_adaptor

# isort: on
# ------------------------------------------------------------------------------
import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterator, Union

from datarobot_genai.core.chat import (
    CustomModelChatResponse,
    CustomModelStreamingResponse,
    resolve_authorization_context,
    to_custom_model_chat_response,
)
from datarobot_genai.core.chat.completions import is_streaming
from datarobot_genai.core.chat.responses import (
    streaming_iterator_to_custom_model_streaming_response,
)
from openai.types.chat import CompletionCreateParams
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
    CompletionCreateParamsStreaming,
)


def load_model(code_dir: str) -> tuple[ThreadPoolExecutor, asyncio.AbstractEventLoop]:
    """The agent is instantiated in this function and returned."""
    thread_pool_executor = ThreadPoolExecutor(1)
    event_loop = asyncio.new_event_loop()
    thread_pool_executor.submit(asyncio.set_event_loop, event_loop).result()
    return (thread_pool_executor, event_loop)


def chat(
    completion_create_params: CompletionCreateParams
    | CompletionCreateParamsNonStreaming
    | CompletionCreateParamsStreaming,
    load_model_result: tuple[ThreadPoolExecutor, asyncio.AbstractEventLoop],
    **kwargs: Any,
) -> Union[CustomModelChatResponse, Iterator[CustomModelStreamingResponse]]:
    """When using the chat endpoint, this function is called.

    Agent inputs are in OpenAI message format and defined as the 'user' portion
    of the input prompt.

    Example:
        prompt = {
            "topic": "Artificial Intelligence",
        }
        client = OpenAI(...)
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"{json.dumps(prompt)}"},
            ],
            extra_body = {
                "environment_var": True,
            },
            ...
        )
    """
    thread_pool_executor, event_loop = load_model_result

    # Change working directory to the directory containing this file.
    # Some agent frameworks expect this for expected pathing.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Load MCP runtime parameters and session secret if configured
    # ["EXTERNAL_MCP_URL", "MCP_DEPLOYMENT_ID", "SESSION_SECRET_KEY"]
    _ = Config()

    # Initialize the authorization context for downstream agents and tools to retrieve
    # access tokens for external services.
    completion_create_params["authorization_context"] = resolve_authorization_context(
        completion_create_params, **kwargs
    )

    # The list of the headers to forward into the Agent and MCP Server.
    incoming_headers = kwargs.get("headers", {}) or {}
    forwarded_headers = {
        k: v
        for k, v in incoming_headers.items()
        if k.lower().startswith("x-datarobot-")
    }
    completion_create_params["forwarded_headers"] = forwarded_headers

    if is_streaming(completion_create_params):
        return _run_streaming(
            thread_pool_executor, event_loop, completion_create_params
        )
    else:
        result = thread_pool_executor.submit(
            event_loop.run_until_complete,
            custompy_adaptor(completion_create_params),
        ).result()
        response_text, pipeline_interactions, usage_metrics = result  # type: ignore[misc]
        return to_custom_model_chat_response(
            response_text,
            pipeline_interactions,
            usage_metrics,  # type: ignore[arg-type]
            model=completion_create_params.get("model"),
        )


def _run_streaming(
    thread_pool_executor: ThreadPoolExecutor,
    event_loop: asyncio.AbstractEventLoop,
    completion_create_params: CompletionCreateParams,
) -> Iterator[CustomModelStreamingResponse]:
    """Run the agent in streaming mode using a queue-based sync/async bridge.

    The entire async pipeline (agent creation, MCP context, streaming iteration)
    runs within a single ``run_until_complete`` call — i.e. one asyncio Task.
    Events are pushed to a thread-safe queue and consumed synchronously on the
    calling thread. This avoids the cross-task cancel-scope errors that occur
    when driving an async generator with repeated ``run_until_complete(anext(...))``
    calls.
    """
    sync_queue: queue.Queue[Any] = queue.Queue()
    _SENTINEL = object()

    async def _drain_to_queue() -> None:
        try:
            async_gen = await custompy_adaptor(completion_create_params)
            async for item in async_gen:  # type: ignore[union-attr]
                sync_queue.put(item)
        except BaseException as exc:
            sync_queue.put(exc)
        finally:
            sync_queue.put(_SENTINEL)

    future = thread_pool_executor.submit(
        event_loop.run_until_complete, _drain_to_queue()
    )

    def _sync_event_iterator() -> Iterator[Any]:
        while True:
            item = sync_queue.get()
            if item is _SENTINEL:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
        future.result()

    return streaming_iterator_to_custom_model_streaming_response(
        _sync_event_iterator(),
        model=completion_create_params.get("model"),
    )
