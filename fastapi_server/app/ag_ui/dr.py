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

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Dict

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    Event,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallChunkEvent,
)
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk
from pydantic import TypeAdapter

from app.ag_ui.base import AGUIAgent
from app.config import Config

logger = logging.getLogger(__name__)


async def _merge_async_generators(
    main_gen: AsyncGenerator[BaseEvent, None],
    heartbeat_gen: AsyncGenerator[BaseEvent, None],
    main_finished_ref: list[bool],
) -> AsyncGenerator[BaseEvent, None]:
    """Merge main stream with heartbeat, stopping heartbeat when main stream finishes."""
    queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue()

    async def _run_main() -> None:
        try:
            async for event in main_gen:
                await queue.put(event)
        except Exception as e:
            logger.exception("Error in main generator", extra={"error": str(e)})
        finally:
            main_finished_ref[0] = True
            await queue.put(None)  # Signal main stream finished

    async def _run_heartbeat() -> None:
        try:
            async for event in heartbeat_gen:
                await queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Error in heartbeat generator", extra={"error": str(e)})

    # Start both generators
    main_task = asyncio.create_task(_run_main())
    heartbeat_task = asyncio.create_task(_run_heartbeat())

    try:
        while True:
            event = await queue.get()
            if event is None:
                # Main stream finished, cancel heartbeat and wait for it
                if not heartbeat_task.done():
                    heartbeat_task.cancel()
                break
            yield event
    finally:
        # Cancel heartbeat if still running
        if not heartbeat_task.done():
            heartbeat_task.cancel()
        # Wait for both tasks to finish
        await asyncio.gather(main_task, heartbeat_task, return_exceptions=True)


async def _heartbeat_generator(
    thread_id: str,
    run_id: str,
    main_finished_ref: list[bool],
    heartbeat_interval: float,
    check_interval: float,
) -> AsyncGenerator[BaseEvent, None]:
    """Generate heartbeat events every 15 seconds until main stream finishes."""

    while True:
        # Sleep in smaller intervals to check if main stream finished
        elapsed = 0.0
        while elapsed < heartbeat_interval:
            if main_finished_ref[0]:
                return
            await asyncio.sleep(min(check_interval, heartbeat_interval - elapsed))
            elapsed += check_interval

        if main_finished_ref[0]:
            return

        # Create a heartbeat event using Event with CUSTOM type
        heartbeat_event = CustomEvent(
            name="Heartbeat",
            value={"thread_id": thread_id, "run_id": run_id},
        )
        yield heartbeat_event


class DataRobotAGUIAgent(AGUIAgent):
    """AG-UI wrapper for a DataRobot Agent."""

    def __init__(
        self,
        name: str,
        config: Config,
        headers: Dict[str, str] | None = None,
        heartbeat_interval: float = 15.0,
        check_interval: float = 1.0,
    ) -> None:
        super().__init__(name)
        self.url = config.agent_endpoint

        agent_headers = {"Authorization": f"Bearer {config.datarobot_api_token}"}
        if headers:
            agent_headers.update(headers)

        self.client = AsyncOpenAI(
            base_url=self.url,
            api_key=config.datarobot_api_token,
            default_headers=agent_headers,
        )
        self.heartbeat_interval = heartbeat_interval
        self.check_interval = check_interval

    async def run(self, input: RunAgentInput) -> AsyncGenerator[BaseEvent, None]:
        # Create shared flag for heartbeat to check if main stream finished
        main_finished_ref = [False]
        # Create heartbeat generator
        heartbeat_gen = _heartbeat_generator(
            input.thread_id,
            input.run_id,
            main_finished_ref,
            self.heartbeat_interval,
            self.check_interval,
        )
        # Merge main stream with heartbeat
        async for event in _merge_async_generators(
            self._handle_stream_events(input), heartbeat_gen, main_finished_ref
        ):
            yield event

    async def _handle_stream_events(
        self, input: RunAgentInput
    ) -> AsyncGenerator[BaseEvent, None]:
        yield RunStartedEvent(thread_id=input.thread_id, run_id=input.run_id)
        try:
            message_id = str(uuid.uuid4())

            text_message_started = False
            run_finished_emitted = False

            logger.debug("Sending request to agent's chat completion endpoint")

            generator: AsyncStream[
                ChatCompletionChunk
            ] = await self.client.chat.completions.create(
                **self._prepare_chat_completions_input(input)
            )
            chunks = 0
            async for chunk in generator:
                chunks += 1
                # Event is already embedded in the chunk, so we don't need to convert it
                if hasattr(chunk, "event"):
                    event = TypeAdapter[Event](Event).validate_python(chunk.event)
                    if isinstance(event, (RunStartedEvent, RunFinishedEvent)):
                        # Normalise IDs to match the wrapper's thread/run context
                        event.thread_id = input.thread_id
                        event.run_id = input.run_id
                        if isinstance(event, RunFinishedEvent):
                            run_finished_emitted = True
                    if event.type not in [
                        EventType.TEXT_MESSAGE_CONTENT,
                        EventType.THINKING_TEXT_MESSAGE_CONTENT,
                    ]:
                        logger.debug(f"Received event: {chunk.event}")
                    yield event
                    continue

                if not chunk.choices:
                    continue
                if len(chunk.choices) > 1:
                    logger.warning("Received more than one choice from chat completion")

                choice = chunk.choices[0]

                if choice.delta.content:
                    if not text_message_started:
                        yield TextMessageStartEvent(message_id=message_id)
                        text_message_started = True
                    yield TextMessageContentEvent(
                        message_id=message_id, delta=choice.delta.content
                    )
                if choice.delta.tool_calls:
                    for tool_call in choice.delta.tool_calls:
                        yield ToolCallChunkEvent(
                            tool_call_id=tool_call.id,
                            tool_call_name=tool_call.function.name
                            if tool_call.function
                            else None,
                            delta=tool_call.function.arguments
                            if tool_call.function
                            else None,
                            parent_message_id=message_id,
                        )
            if chunks == 0:
                raise RuntimeError(
                    "No response received from the agent. Please check if agent supports streaming."
                )

            logger.debug("Processed all chat completions")

            if text_message_started:
                yield TextMessageEndEvent(message_id=message_id)

            if not run_finished_emitted:
                yield RunFinishedEvent(thread_id=input.thread_id, run_id=input.run_id)

        except Exception as e:
            logger.exception("Error during agent run")
            yield RunErrorEvent(message=str(e))

    def _prepare_chat_completions_input(self, input: RunAgentInput) -> Dict[str, Any]:
        messages = []
        for input_message in input.messages:
            msg: Dict[str, Any] = {
                "role": input_message.role,
                "content": input_message.content,
            }

            if input_message.role == "assistant":
                # OpenAI-compatible APIs require tool_calls on assistant messages so that
                # subsequent tool messages (with tool_call_id) can be correlated.
                raw_tool_calls = getattr(input_message, "tool_calls", None)
                if raw_tool_calls:
                    tool_calls_payload = []
                    for tc in raw_tool_calls:
                        raw_id = (
                            tc.get("id")
                            if isinstance(tc, dict)
                            else getattr(tc, "id", None)
                        )
                        id_str = str(raw_id).strip() if raw_id is not None else ""
                        if not id_str or id_str == "None":
                            raise ValueError(
                                "Assistant tool_calls must have a non-empty id so "
                                "tool messages can be correlated; got missing or None id."
                            )
                        tc_id = raw_id
                        if isinstance(tc, dict):
                            fn = tc.get("function") or {}
                            tool_calls_payload.append(
                                {
                                    "id": str(tc_id),
                                    "type": "function",
                                    "function": {
                                        "name": fn.get("name", ""),
                                        "arguments": fn.get("arguments", ""),
                                    },
                                }
                            )
                        else:
                            fn = getattr(tc, "function", None)
                            tool_calls_payload.append(
                                {
                                    "id": str(tc_id),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(fn, "name", "") if fn else "",
                                        "arguments": (
                                            getattr(fn, "arguments", "") or ""
                                        )
                                        if fn
                                        else "",
                                    },
                                }
                            )
                    msg["tool_calls"] = tool_calls_payload

            elif input_message.role == "tool":
                tool_call_id = getattr(input_message, "tool_call_id", None) or getattr(
                    input_message, "id", None
                )
                if tool_call_id is not None:
                    msg["tool_call_id"] = str(tool_call_id)
                err = getattr(input_message, "error", None)
                if err is not None:
                    msg["error"] = str(err)
            messages.append(msg)
        return {
            "messages": messages,
            "model": "unknown",
            "stream": True,
        }
