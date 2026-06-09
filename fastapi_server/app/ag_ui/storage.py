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
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, final
from uuid import UUID, uuid4

from ag_ui.core import (
    BaseEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageChunkEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingTextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallChunkEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

from app.ag_ui.base import AGUIAgent
from app.ag_ui.error_codes import ErrorCodes
from app.ag_ui.translate import translate_messages
from app.chats import Chat, ChatCreate
from app.messages import (
    Message,
    MessageCreate,
    MessageReasoning,
    MessageReasoningCreate,
    MessageReasoningUpdate,
    MessageToolCall,
    MessageToolCallCreate,
    MessageToolCallUpdate,
    MessageUpdate,
    Role,
)
from app.repo_types import ChatRepositoryLike, MessageRepositoryLike

logger = logging.getLogger(__name__)


@dataclass
class StorageStateMachineState:
    active_step: str | None = None
    current_event_timestamp: datetime = datetime.fromtimestamp(0)
    active_reasoning_title: str | None = None
    active_reasoning: MessageReasoning | None = None
    active_tool_call: MessageToolCall | None = None
    active_message: Message | None = None
    # Buffering for content to reduce database updates
    buffered_message_content: str = ""
    buffered_tool_call_arguments: str = ""
    buffered_reasoning_content: str = ""


@final
class AGUIAgentWithStorage(AGUIAgent):
    """A wrapper for an agent that stores messages."""

    _epoch_seconds_warning_emitted = False

    def __init__(
        self,
        name: str,
        user_id: UUID,
        inner: AGUIAgent,
        chat_repo: ChatRepositoryLike,
        message_repo: MessageRepositoryLike,
        minimal_chunk_to_persist: int = 5000,
        max_queue_size: int = 10_000,
        put_timeout: float = 0.1,
    ):
        """
        Initialize an agent.

        Args:
            name (str): The name of this agent.
            user_id (UUID): The ID of the user creating this message
            inner (AGUIAgent): The agent this wraps. Only requirement is that the agent uses UUIDs as its message id format.
            chat_repo: Chat repository (SQLite or memory-service implementation).
            message_repo: Message repository (SQLite or memory-service implementation).
            max_queue_size (int): Maximum number of events buffered in the storage queue. Defaults to 10,000.
            put_timeout (float): Maximum seconds to wait when enqueuing an event. Defaults to 0.1.
        """
        super().__init__(name)
        if isinstance(inner, AGUIAgentWithStorage):
            raise ValueError(
                "Cannot wrap an AGUIAgentWithStorage with a second storage layer."
            )
        self._user_id = user_id
        self._inner = inner
        self._chat_repo = chat_repo
        self._message_repo = message_repo
        self._minimal_chunk_to_persist = minimal_chunk_to_persist
        self._max_queue_size = max_queue_size
        self._put_timeout = put_timeout
        self._event_queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._consumer_task: asyncio.Task[None] | None = None
        self._current_chat: Chat | None = None

    async def run(self, input: RunAgentInput) -> AsyncGenerator[BaseEvent, None]:
        """
        This persists any incoming new user messages, runs the inner agent, and persists any messages.

        Args:
            input (RunAgentInput): The input

        Returns:
            AsyncGenerator[BaseEvent, None]: The inner agents event
        """
        existing_chat: Chat

        logger.debug(
            "Fetching initial chat",
            extra={"thread_id": input.thread_id, "user": str(self._user_id)},
        )

        if maybe_chat := await self._chat_repo.get_chat_by_thread_id(
            self._user_id,
            input.thread_id,
        ):
            existing_chat = maybe_chat
        else:
            logger.debug(
                "Creating initial chat",
                extra={"thread_id": input.thread_id, "user": str(self._user_id)},
            )

            if (
                input.messages
                and isinstance(input.messages[0].content, str)
                and len(input.messages[0].content.strip()) > 0
            ):
                chat_name = input.messages[0].content[:20].strip()
            else:
                chat_name = "New Chat"

            existing_chat = await self._chat_repo.create_chat(
                ChatCreate(
                    user_uuid=self._user_id,
                    name=chat_name,
                    thread_id=input.thread_id,
                )
            )

        for message in input.messages:
            existing_message = await self._message_repo.get_message_by_agui_id(
                existing_chat.uuid, message.id
            )
            if existing_message:
                if existing_chat.uuid != existing_message.chat_id:
                    yield RunErrorEvent(
                        message="Messages do not all belong to the same chat",
                        code=ErrorCodes.INVALID_INPUT.value,
                    )
                    return
            else:
                if message.role != "user":
                    yield RunErrorEvent(
                        message="The user cannot create new non-user messages.",
                        code=ErrorCodes.INVALID_INPUT.value,
                    )
                    return

                await self._message_repo.create_message(
                    MessageCreate(
                        chat_id=existing_chat.uuid,
                        role=Role.USER.value,
                        agui_id=message.id,
                        name=message.name or "",
                        content=message.content,
                        error=None,
                        in_progress=False,
                    )
                )

        # After persisting any new user messages, rebuild the RunAgentInput messages
        # from the full stored chat so downstream agents receive conversation history.
        existing_messages = await self._message_repo.get_chat_messages(
            existing_chat.uuid
        )
        input.messages = list(translate_messages(existing_messages))  # type: ignore[arg-type]

        # Store chat for consumer task to access
        self._current_chat = existing_chat

        # Re-create the queue for this run
        self._event_queue = asyncio.Queue(maxsize=self._max_queue_size)

        # Launch background consumer task
        self._consumer_task = asyncio.create_task(self._storage_consumer(existing_chat))

        try:
            async for event in self._inner.run(input):
                logger.debug("Queuing event for storage %s", event)

                # We're making sure the timestamp is set as we want to use it for `created_at` on messages
                # This addresses a possible edge case of new user messages being sent while agent is responding
                # to protect against the timeline of chat history going out of order in case messages take too long.
                if not event.timestamp:
                    event.timestamp = int(
                        datetime.now(timezone.utc).timestamp() * 1_000
                    )

                if (
                    not self._epoch_seconds_warning_emitted
                    and event.timestamp < 100_000_000_000
                ):
                    # https://docs.ag-ui.com/concepts/events - doesn't specify epoch seconds or milliseconds for timestamp
                    # Current epoch milli is on order of 1.7 * 10^12, so <1*10^11 is probably the wrong unit
                    # So far in testing upstream agent frameworks
                    logger.warning(
                        "Received a timestamp that is probably epoch seconds when expecting epoch millis!"
                    )
                    self._epoch_seconds_warning_emitted = True

                # Immediately queue and yield event without waiting for storage
                try:
                    await asyncio.wait_for(
                        self._event_queue.put(event), timeout=self._put_timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Max queue %d size reached and event could not be put for %d seconds.",
                        self._max_queue_size,
                        self._put_timeout,
                    )
                yield event
        finally:
            # Signal consumer to stop and wait for cleanup
            try:
                await asyncio.wait_for(
                    self._event_queue.put(None), timeout=self._put_timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Max queue %d size reached and finalization could not be put for %d seconds.",
                    self._max_queue_size,
                    self._put_timeout,
                )
            try:
                await self._consumer_task
            except Exception:
                logger.warning("Storage consumer task failed", exc_info=True)
            finally:
                self._consumer_task = None

    async def _storage_consumer(self, existing_chat: Chat) -> None:
        """
        Background task that consumes events from the queue and persists them to storage.
        Runs independently from the event emission stream.

        Events are drained in batches, and each batch is persisted inside a single
        repository transaction so all of its repository calls share one database
        session, one transaction, and one commit rather than one of each per call.

        Args:
            existing_chat (Chat): The chat to persist events for.
        """
        state = StorageStateMachineState()

        try:
            finished = False
            while not finished:
                # Get event from queue; None signals completion
                event = await self._event_queue.get()
                if event is None:
                    break

                # Drain whatever else is already queued into one batch.
                batch = [event]
                while not finished:
                    try:
                        next_event = self._event_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if next_event is None:
                        finished = True
                        break
                    batch.append(next_event)

                async with self._message_repo.transaction():
                    for event in batch:
                        try:
                            state = await self._process_event(
                                state, existing_chat, event
                            )
                        except Exception as e:
                            logger.error(
                                f"Error processing event in storage consumer: {e}",
                                exc_info=True,
                            )
                            # Continue consuming events despite errors
                            continue
        except Exception as e:
            logger.error(
                f"Storage consumer task failed: {e}",
                exc_info=True,
            )
        finally:
            # Ensure final flush on task completion
            try:
                async with self._message_repo.transaction():
                    await self._flush_message_buffer(state)
                    await self._flush_reasoning_buffer(state)
                    await self._flush_tool_call_buffer(state)
            except Exception as e:
                logger.error(
                    f"Error during final flush in storage consumer: {e}",
                    exc_info=True,
                )

    async def _process_event(
        self,
        state: StorageStateMachineState,
        existing_chat: Chat,
        event: BaseEvent,
    ) -> StorageStateMachineState:
        """
        Apply a single event to the storage state machine, persisting as needed.

        Args:
            state (StorageStateMachineState): The current state machine state.
            existing_chat (Chat): The chat to persist events for.
            event (BaseEvent): The event to process.

        Returns:
            StorageStateMachineState: The (possibly reset) state machine state.
        """
        state.current_event_timestamp = self._epoch_milli_or_now(event.timestamp)

        if isinstance(event, RunStartedEvent):
            state = StorageStateMachineState()
        if isinstance(event, RunFinishedEvent):
            # Flush remaining buffers
            await self._flush_message_buffer(state)
            await self._flush_reasoning_buffer(state)
            await self._flush_tool_call_buffer(state)

            if state.active_message:
                await self._message_repo.update_message(
                    state.active_message.uuid,
                    MessageUpdate(in_progress=False),
                )
            if state.active_reasoning:
                await self._message_repo.update_message_reasoning(
                    state.active_reasoning.uuid,
                    MessageReasoningUpdate(in_progress=False),
                )
            if state.active_tool_call:
                await self._message_repo.update_message_tool_call(
                    state.active_tool_call.uuid,
                    MessageToolCallUpdate(in_progress=False),
                )
        if isinstance(event, RunErrorEvent):
            # Flush remaining buffers before marking as errored
            await self._flush_message_buffer(state)
            await self._flush_reasoning_buffer(state)
            await self._flush_tool_call_buffer(state)

            if event.code:
                error = f"[{event.code}] {event.message}"
            else:
                error = event.message
            if state.active_message:
                await self._message_repo.update_message(
                    state.active_message.uuid,
                    MessageUpdate(in_progress=False, error=error),
                )
            if state.active_reasoning:
                await self._message_repo.update_message_reasoning(
                    state.active_reasoning.uuid,
                    MessageReasoningUpdate(in_progress=False, error=error),
                )
            if state.active_tool_call:
                await self._message_repo.update_message_tool_call(
                    state.active_tool_call.uuid,
                    MessageToolCallUpdate(in_progress=False, error=error),
                )

        if isinstance(event, StepStartedEvent):
            state.active_step = event.step_name
        if isinstance(event, StepFinishedEvent):
            state.active_step = None

        await self._handle_text_message_events(state, existing_chat, event)
        await self._handle_tool_call_events(state, existing_chat, event)
        await self._handle_reasoning_event(state, existing_chat, event)

        return state

    async def _handle_reasoning_event(
        self, state: StorageStateMachineState, existing_chat: Chat, event: BaseEvent
    ) -> None:
        # TODO: This is a placeholder as actual AGUI Reasoning is in draft https://docs.ag-ui.com/drafts/reasoning.
        # Should mostly be as simple as swapping the (deprecated) `Thinking...` events for `Reasoning...` events
        # when that draft is adopted.
        if isinstance(event, ThinkingStartEvent):
            state.active_reasoning_title = event.title
        if isinstance(event, ThinkingEndEvent):
            await self._flush_reasoning_buffer(state)
            state.active_reasoning_title = None
            if state.active_reasoning:
                await self._message_repo.update_message_reasoning(
                    state.active_reasoning.uuid,
                    MessageReasoningUpdate(in_progress=False),
                )
                state.active_reasoning = None
        if isinstance(event, ThinkingTextMessageStartEvent):
            await self._ensure_message_exists(state, existing_chat, None, None)
            assert state.active_message, "Message created"
            await self._message_repo.create_message_reasoning(
                MessageReasoningCreate(
                    role=Role.REASONING.value,
                    message_uuid=state.active_message.uuid,
                    name=state.active_reasoning_title or "",
                    created_at=state.current_event_timestamp,
                )
            )
        if isinstance(event, ThinkingTextMessageContentEvent):
            await self._ensure_message_exists(state, existing_chat, None, None)
            assert state.active_message, "Message created"
            if not state.active_reasoning:
                # We need to ensure that active message is loaded here so that `reasonings` is live.
                assert state.active_message.chat_id and state.active_message.agui_id
                state.active_message = await self._message_repo.get_message_by_agui_id(
                    state.active_message.chat_id, state.active_message.agui_id
                )
                assert state.active_message
                if latest_reasoning := next(
                    iter(
                        sorted(
                            filter(
                                lambda r: r.in_progress, state.active_message.reasonings
                            ),
                            key=lambda r: r.created_at,
                            reverse=True,
                        )
                    ),
                    None,
                ):
                    state.active_reasoning = latest_reasoning
                else:
                    state.active_reasoning = (
                        await self._message_repo.create_message_reasoning(
                            MessageReasoningCreate(
                                role=Role.REASONING.value,
                                message_uuid=state.active_message.uuid,
                                name=state.active_reasoning_title or "",
                                created_at=state.current_event_timestamp,
                            ),
                        )
                    )
            assert state.active_reasoning
            # Buffer content instead of updating immediately
            if isinstance(event.delta, str):
                state.buffered_reasoning_content += event.delta
            elif isinstance(event.delta, list):
                state.buffered_reasoning_content += "\n" + json.dumps(event.delta)
            else:
                logger.warning(
                    "Received reasoning '%s' of unanticipated type.", event.delta
                )

            # Flush buffer if it gets too large
            if len(state.buffered_reasoning_content) >= self._minimal_chunk_to_persist:
                await self._flush_reasoning_buffer(state)
        if isinstance(event, ThinkingTextMessageEndEvent):
            await self._ensure_message_exists(state, existing_chat, None, None)
            assert state.active_message, "Message created"
            if not state.active_reasoning:
                if latest_reasoning := next(
                    iter(
                        sorted(
                            filter(
                                lambda r: r.in_progress, state.active_message.reasonings
                            ),
                            key=lambda r: r.created_at,
                            reverse=True,
                        )
                    ),
                    None,
                ):
                    state.active_reasoning = latest_reasoning
                else:
                    state.active_reasoning = (
                        await self._message_repo.create_message_reasoning(
                            MessageReasoningCreate(
                                role=Role.REASONING.value,
                                message_uuid=state.active_message.uuid,
                                name=state.active_reasoning or "",
                                created_at=state.current_event_timestamp,
                            )
                        )
                    )
            assert state.active_reasoning
            # Flush any remaining buffered content
            await self._flush_reasoning_buffer(state)
            await self._message_repo.update_message_reasoning(
                state.active_reasoning.uuid, MessageReasoningUpdate(in_progress=False)
            )
            state.active_reasoning = None

    async def _handle_tool_call_events(
        self, state: StorageStateMachineState, existing_chat: Chat, event: BaseEvent
    ) -> None:
        if isinstance(event, ToolCallStartEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                event.parent_message_id,
                None,
            )
            await self._ensure_tool_call_exists(
                state, event.tool_call_id, event.tool_call_name
            )
        if isinstance(event, ToolCallArgsEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                None,
                None,
            )
            await self._ensure_tool_call_exists(state, event.tool_call_id, None)
            assert state.active_tool_call, "Tool Call Created"
            # Buffer arguments instead of updating immediately
            state.buffered_tool_call_arguments += event.delta

            # Flush buffer if it gets too large
            if (
                len(state.buffered_tool_call_arguments)
                >= self._minimal_chunk_to_persist
            ):
                await self._flush_tool_call_buffer(state)
        if isinstance(event, ToolCallResultEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                None,
                None,
            )
            await self._ensure_tool_call_exists(state, event.tool_call_id, None)
            assert state.active_tool_call, "Tool Call Created"
            await self._message_repo.update_message_tool_call(
                state.active_tool_call.uuid,
                MessageToolCallUpdate(content=event.content),
            )
        if isinstance(event, ToolCallEndEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                None,
                None,
            )
            await self._ensure_tool_call_exists(state, event.tool_call_id, None)
            assert state.active_tool_call, "Tool Call Created"
            # Flush any remaining buffered arguments
            await self._flush_tool_call_buffer(state)
            await self._message_repo.update_message_tool_call(
                state.active_tool_call.uuid, MessageToolCallUpdate(in_progress=False)
            )
            state.active_tool_call.in_progress = False
        if isinstance(event, ToolCallChunkEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                event.parent_message_id
                or (state.active_message and state.active_message.agui_id)
                or str(uuid4()),
                None,
            )
            await self._ensure_tool_call_exists(
                state,
                event.tool_call_id
                or (state.active_tool_call and state.active_tool_call.tool_call_id)
                or str(uuid4()),
                event.tool_call_name,
            )
            assert state.active_tool_call, "Tool Call Created"
            # Buffer arguments for chunk events too; the tool call is closed out when
            # the next tool call starts or the run finishes.
            state.buffered_tool_call_arguments += event.delta or ""

            # Flush buffer if it gets too large
            if (
                len(state.buffered_tool_call_arguments)
                >= self._minimal_chunk_to_persist
            ):
                await self._flush_tool_call_buffer(state)

    async def _handle_text_message_events(
        self,
        state: StorageStateMachineState,
        existing_chat: Chat,
        event: BaseEvent,
    ) -> None:
        if isinstance(event, TextMessageStartEvent):
            await self._ensure_message_exists(
                state, existing_chat, event.message_id, event.role
            )
        if isinstance(event, TextMessageContentEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                event.message_id,
                None,
            )
            assert state.active_message, "Active message created."
            # Buffer content instead of updating immediately
            state.buffered_message_content += event.delta

            # Flush buffer if it gets too large
            if len(state.buffered_message_content) >= self._minimal_chunk_to_persist:
                await self._flush_message_buffer(state)
        if isinstance(event, TextMessageEndEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                event.message_id,
                None,
            )
            assert state.active_message, "Active message created."
            # Flush any remaining buffered content
            await self._flush_message_buffer(state)
            await self._message_repo.update_message(
                state.active_message.uuid, MessageUpdate(in_progress=False)
            )
        if isinstance(event, TextMessageChunkEvent):
            await self._ensure_message_exists(
                state,
                existing_chat,
                event.message_id
                or (state.active_message and state.active_message.agui_id)
                or str(uuid4()),
                None,
            )
            assert state.active_message, "Active message created."
            # Buffer content instead of updating immediately; the message is closed
            # out when the next message starts or the run finishes.
            state.buffered_message_content += event.delta or ""

            # Flush buffer if it gets too large
            if len(state.buffered_message_content) >= self._minimal_chunk_to_persist:
                await self._flush_message_buffer(state)

    async def _flush_message_buffer(self, state: StorageStateMachineState) -> None:
        """Flush buffered message content to storage."""
        if state.active_message and state.buffered_message_content:
            state.active_message.content += state.buffered_message_content
            await self._message_repo.update_message(
                state.active_message.uuid,
                MessageUpdate(content=state.active_message.content),
            )
            state.buffered_message_content = ""

    async def _flush_tool_call_buffer(self, state: StorageStateMachineState) -> None:
        """Flush buffered tool call arguments to storage."""
        if state.active_tool_call and state.buffered_tool_call_arguments:
            state.active_tool_call.arguments += state.buffered_tool_call_arguments
            await self._message_repo.update_message_tool_call(
                state.active_tool_call.uuid,
                MessageToolCallUpdate(arguments=state.active_tool_call.arguments),
            )
            state.buffered_tool_call_arguments = ""

    async def _flush_reasoning_buffer(self, state: StorageStateMachineState) -> None:
        """Flush buffered reasoning content to storage."""
        if state.active_reasoning and state.buffered_reasoning_content:
            state.active_reasoning.content += state.buffered_reasoning_content
            await self._message_repo.update_message_reasoning(
                state.active_reasoning.uuid,
                MessageReasoningUpdate(content=state.active_reasoning.content),
            )
            state.buffered_reasoning_content = ""

    async def _ensure_message_exists(
        self,
        state: StorageStateMachineState,
        existing_chat: Chat,
        agui_id: str | None,
        role: str | None,
    ) -> None:
        """
        Return the assistant message in the chat matching the AGUI message ID. Refreshes the message if it exists.

        Args:
            active_step (str | None): The current step (can be None).
            existing_chat (Chat): The current chat.
            active_message (Message | None): The known current active message.
            agui_id (str | None): The desired message (if not provided, any assistant message will do).
            role (str | None): The role of the user leaving this message. Defaults to ASSISTANT.

        Returns:
            Message: _description_
        """
        active_message = state.active_message
        # If we are starting a new message, close out prior message.
        if agui_id and active_message and active_message.agui_id != agui_id:
            message_update = MessageUpdate(in_progress=False)
            if state.buffered_message_content:
                active_message.content += state.buffered_message_content
                message_update.content = active_message.content
            await self._message_repo.update_message(active_message.uuid, message_update)
            active_message = None

        if not active_message:
            state.buffered_message_content = ""
            active_role: str | None = active_message.role if active_message else None
            active_agui_id: str | None = (
                active_message.agui_id if active_message else None
            )

            if agui_id:
                if retrieved_message := await self._message_repo.get_message_by_agui_id(
                    existing_chat.uuid, agui_id
                ):
                    active_message = retrieved_message
                else:
                    active_message = await self._message_repo.create_message(
                        MessageCreate(
                            step=state.active_step,
                            chat_id=existing_chat.uuid,
                            agui_id=agui_id,
                            role=role or active_role or Role.ASSISTANT.value,
                            name=self.name,
                            content="",
                            error=None,
                            in_progress=True,
                            created_at=state.current_event_timestamp,
                        )
                    )
            else:
                last_message = (
                    await self._message_repo.get_last_messages([existing_chat.uuid])
                )[existing_chat.uuid]
                if last_message.role == (role or Role.ASSISTANT.value):
                    active_message = last_message
                else:
                    active_message = await self._message_repo.create_message(
                        MessageCreate(
                            step=state.active_step,
                            chat_id=existing_chat.uuid,
                            agui_id=agui_id or active_agui_id,
                            role=role or active_role or Role.ASSISTANT.value,
                            name=self.name,
                            content="",
                            error=None,
                            in_progress=True,
                            created_at=state.current_event_timestamp,
                        )
                    )

        state.active_message = active_message

    async def _ensure_tool_call_exists(
        self,
        state: StorageStateMachineState,
        tool_call_id: str,
        tool_call_name: str | None,
    ) -> None:
        if not state.active_message:
            raise RuntimeError(
                f"Creating {tool_call_id} with no corresponding active message"
            )

        prior_tool_call = state.active_tool_call
        if (
            prior_tool_call
            and prior_tool_call.agui_id == tool_call_id
            and prior_tool_call.message_uuid == state.active_message.uuid
        ):
            return

        # Starting a different tool call: flush buffered arguments to the prior one
        # and close it out.
        if prior_tool_call:
            await self._flush_tool_call_buffer(state)
            if prior_tool_call.in_progress:
                await self._message_repo.update_message_tool_call(
                    prior_tool_call.uuid, MessageToolCallUpdate(in_progress=False)
                )
                prior_tool_call.in_progress = False

        if not (
            active_tool_call := await self._message_repo.get_tool_call_by_agui_id(
                state.active_message.uuid, tool_call_id
            )
        ):
            active_tool_call = await self._message_repo.create_message_tool_call(
                MessageToolCallCreate(
                    tool_call_id=tool_call_id,
                    agui_id=tool_call_id,
                    message_uuid=state.active_message.uuid,
                    role=Role.TOOL.value,
                    name=tool_call_name or "UNKNOWN",
                    created_at=state.current_event_timestamp,
                )
            )
        state.active_tool_call = active_tool_call

    @staticmethod
    def _epoch_milli_or_now(timestamp: int | None) -> datetime:
        if timestamp is None:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(timestamp / 1_000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return datetime.now(timezone.utc)
