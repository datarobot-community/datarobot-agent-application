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
import uuid
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Coroutine, Iterator
from unittest.mock import patch

import pytest
from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    Message,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallChunkEvent,
)
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)

from app.ag_ui.dr import DataRobotAGUIAgent
from app.config import Config
from tests.ag_ui.conftest import run_input


@pytest.fixture(scope="function")
def set_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[ChatCompletionChunk]], None]:
    """Fixture to mock OpenAI client responses"""
    mock_responses: list[ChatCompletionChunk] = []

    def mock_create(
        *args: Any, **kwargs: Any
    ) -> Coroutine[None, None, AsyncIterator[ChatCompletionChunk]]:
        async def foo() -> AsyncIterator[ChatCompletionChunk]:
            return generate(*mock_responses)

        return foo()

    monkeypatch.setattr(
        "openai.resources.chat.completions.AsyncCompletions.create", mock_create
    )

    def set(responses: list[ChatCompletionChunk]) -> None:
        mock_responses.clear()
        mock_responses.extend(responses)

    return set


@pytest.fixture(scope="function")
def set_completions_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[ChatCompletionChunk]], None]:
    """Fixture to mock OpenAI client responses"""
    mock_responses: list[ChatCompletionChunk] = []

    def mock_create(
        *args: Any, **kwargs: Any
    ) -> Coroutine[None, None, AsyncIterator[ChatCompletionChunk]]:
        async def foo() -> AsyncIterator[ChatCompletionChunk]:
            return generate_slow(*mock_responses)

        return foo()

    monkeypatch.setattr(
        "openai.resources.chat.completions.AsyncCompletions.create", mock_create
    )

    def set(responses: list[ChatCompletionChunk]) -> None:
        mock_responses.clear()
        mock_responses.extend(responses)

    return set


@pytest.fixture(scope="function")
def error_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[BaseException], None]:
    """Fixture to mock OpenAI client responses"""
    exception: list[BaseException] = []

    def mock_create(
        *args: Any, **kwargs: Any
    ) -> Coroutine[None, None, AsyncIterator[ChatCompletionChunk]]:
        async def foo() -> AsyncIterator[ChatCompletionChunk]:
            raise exception[0]

        return foo()

    monkeypatch.setattr(
        "openai.resources.chat.completions.AsyncCompletions.create", mock_create
    )

    def set(e: BaseException) -> None:
        exception.append(e)

    return set


_TEST_AGENT_NAME = "Test Agent"


@pytest.fixture
def model() -> Iterator[str]:
    yield "datarobot/openai/gpt-5-mini"


@pytest.fixture
def url() -> Iterator[str]:
    yield "https://localhost:8842"


@pytest.fixture
def dr_agui_agent(config: Config) -> Iterator[DataRobotAGUIAgent]:
    yield DataRobotAGUIAgent(_TEST_AGENT_NAME, config)


@pytest.fixture
def dr_agui_agent_heartbeat(config: Config) -> Iterator[DataRobotAGUIAgent]:
    yield DataRobotAGUIAgent(
        _TEST_AGENT_NAME, config, heartbeat_interval=0.1, check_interval=0.02
    )


async def generate(*args: Any) -> AsyncIterator[Any]:
    for a in args:
        yield a


async def generate_slow(*args: Any) -> AsyncIterator[Any]:
    for a in args:
        await asyncio.sleep(0.1)
        yield a


async def run(agent: DataRobotAGUIAgent, *messages: Message) -> list[BaseEvent]:
    result = []
    async for event in agent.run(run_input(*messages)):
        result.append(event)
    return result


def chat_completions(
    *args: tuple[str, list[ChoiceDeltaToolCall]],
) -> list[ChatCompletionChunk]:
    return [
        ChatCompletionChunk(
            id="",
            model="",
            created=0,
            object="chat.completion.chunk",
            choices=[
                Choice(
                    finish_reason=None,
                    index=0,
                    delta=ChoiceDelta(content=content, tool_calls=tools),
                )
            ],
        )
        for content, tools in args
    ]


async def test_run_empty_response(
    set_completions: Callable[[list[ChoiceDelta]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    set_completions([])
    with patch("uuid.uuid4") as uuid4:
        stub_uuid = "8825aa49-97ce-4fdf-9807-2ad9b4158acc"
        uuid4.return_value = uuid.UUID(stub_uuid)
        result = await run(dr_agui_agent)
        assert result == [
            RunStartedEvent(thread_id="thread", run_id="run"),
            RunErrorEvent(
                message="No response received from the agent. Please check if agent supports streaming."
            ),
        ]


async def test_run_failed_response(
    error_completions: Callable[[BaseException], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    error_completions(RuntimeError("Error"))
    result = await run(dr_agui_agent)
    with patch("uuid.uuid4") as uuid4:
        stub_uuid = "8825aa49-97ce-4fdf-9807-2ad9b4158acc"
        uuid4.return_value = uuid.UUID(stub_uuid)
        result = await run(dr_agui_agent)
        assert result == [
            RunStartedEvent(thread_id="thread", run_id="run"),
            RunErrorEvent(message="Error"),
        ]


async def test_run_single_message(
    set_completions: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    set_completions(chat_completions(("Hi", [])))
    with patch("uuid.uuid4") as uuid4:
        stub_uuid = "8825aa49-97ce-4fdf-9807-2ad9b4158acc"
        uuid4.return_value = uuid.UUID(stub_uuid)
        result = await run(dr_agui_agent)
        assert result == [
            RunStartedEvent(thread_id="thread", run_id="run"),
            TextMessageStartEvent(
                message_id=stub_uuid,
            ),
            TextMessageContentEvent(message_id=stub_uuid, delta="Hi"),
            TextMessageEndEvent(message_id=stub_uuid),
            RunFinishedEvent(thread_id="thread", run_id="run"),
        ]


async def test_run_complex(
    set_completions: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    set_completions(
        chat_completions(
            (
                "Hi",
                [
                    ChoiceDeltaToolCall(
                        index=0,
                        id="c1",
                        function=ChoiceDeltaToolCallFunction(arguments="a1", name="n1"),
                    ),
                    ChoiceDeltaToolCall(
                        index=0,
                        id="c2",
                    ),
                ],
            ),
            ("Bye", []),
        )
    )
    with patch("uuid.uuid4") as uuid4:
        uuid4.return_value = uuid.UUID("8825aa49-97ce-4fdf-9807-2ad9b4158acc")
        result = await run(dr_agui_agent)
        assert result == [
            RunStartedEvent(thread_id="thread", run_id="run"),
            TextMessageStartEvent(message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc"),
            TextMessageContentEvent(
                message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc", delta="Hi"
            ),
            ToolCallChunkEvent(
                parent_message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc",
                tool_call_id="c1",
                delta="a1",
                tool_call_name="n1",
            ),
            ToolCallChunkEvent(
                parent_message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc",
                tool_call_id="c2",
                delta=None,
                tool_call_name=None,
            ),
            TextMessageContentEvent(
                message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc", delta="Bye"
            ),
            TextMessageEndEvent(message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc"),
            RunFinishedEvent(thread_id="thread", run_id="run"),
        ]


async def test_run_complex_slow_stream(
    set_completions_slow: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent_heartbeat: DataRobotAGUIAgent,
) -> None:
    set_completions_slow(
        chat_completions(
            (
                "Hi",
                [
                    ChoiceDeltaToolCall(
                        index=0,
                        id="c1",
                        function=ChoiceDeltaToolCallFunction(arguments="a1", name="n1"),
                    ),
                    ChoiceDeltaToolCall(
                        index=0,
                        id="c2",
                    ),
                ],
            ),
            ("Bye", []),
        )
    )
    with patch("uuid.uuid4") as uuid4:
        uuid4.return_value = uuid.UUID("8825aa49-97ce-4fdf-9807-2ad9b4158acc")
        result = await run(dr_agui_agent_heartbeat)
        assert result == [
            RunStartedEvent(thread_id="thread", run_id="run"),
            TextMessageStartEvent(message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc"),
            TextMessageContentEvent(
                message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc", delta="Hi"
            ),
            ToolCallChunkEvent(
                parent_message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc",
                tool_call_id="c1",
                delta="a1",
                tool_call_name="n1",
            ),
            ToolCallChunkEvent(
                parent_message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc",
                tool_call_id="c2",
                delta=None,
                tool_call_name=None,
            ),
            CustomEvent(
                name="Heartbeat", value={"thread_id": "thread", "run_id": "run"}
            ),
            TextMessageContentEvent(
                message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc", delta="Bye"
            ),
            TextMessageEndEvent(message_id="8825aa49-97ce-4fdf-9807-2ad9b4158acc"),
            RunFinishedEvent(thread_id="thread", run_id="run"),
        ]


def _make_event_chunk(event_dict: dict[str, Any]) -> ChatCompletionChunk:
    """Create a ChatCompletionChunk with an embedded AG-UI event."""
    chunk = ChatCompletionChunk(
        id="", model="", created=0, object="chat.completion.chunk", choices=[]
    )
    object.__setattr__(chunk, "event", event_dict)
    return chunk


async def test_embedded_run_finished_normalises_ids_and_suppresses_duplicate(
    set_completions: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    """When the agent stream contains a RUN_FINISHED with wrong IDs, the wrapper
    normalises thread_id/run_id and does NOT emit a second RunFinishedEvent."""
    set_completions(
        [
            *chat_completions(("Hi", [])),
            _make_event_chunk(
                {
                    "type": "RUN_FINISHED",
                    "threadId": "wrong-thread",
                    "runId": "wrong-run",
                }
            ),
        ]
    )

    with patch("uuid.uuid4") as uuid4:
        uuid4.return_value = uuid.UUID("8825aa49-97ce-4fdf-9807-2ad9b4158acc")
        result = await run(dr_agui_agent)

    run_finished = [e for e in result if isinstance(e, RunFinishedEvent)]
    assert len(run_finished) == 1, (
        f"Expected exactly 1 RunFinishedEvent, got {[type(e).__name__ for e in result]}"
    )
    assert run_finished[0].thread_id == "thread"
    assert run_finished[0].run_id == "run"


async def test_embedded_run_started_normalises_ids(
    set_completions: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    """An embedded RUN_STARTED from the agent stream has its IDs normalised
    to match the wrapper's input thread_id/run_id."""
    set_completions(
        [
            _make_event_chunk(
                {
                    "type": "RUN_STARTED",
                    "threadId": "wrong-thread",
                    "runId": "wrong-run",
                }
            ),
            *chat_completions(("Hi", [])),
        ]
    )

    with patch("uuid.uuid4") as uuid4:
        uuid4.return_value = uuid.UUID("8825aa49-97ce-4fdf-9807-2ad9b4158acc")
        result = await run(dr_agui_agent)

    run_started = [e for e in result if isinstance(e, RunStartedEvent)]
    for evt in run_started:
        assert evt.thread_id == "thread"
        assert evt.run_id == "run"


async def test_fallback_run_finished_when_agent_does_not_emit_one(
    set_completions: Callable[[list[ChatCompletionChunk]], None],
    dr_agui_agent: DataRobotAGUIAgent,
) -> None:
    """When the agent stream contains no embedded RUN_FINISHED, the wrapper
    emits its own so the client always receives exactly one."""
    set_completions(chat_completions(("Hi", [])))

    with patch("uuid.uuid4") as uuid4:
        uuid4.return_value = uuid.UUID("8825aa49-97ce-4fdf-9807-2ad9b4158acc")
        result = await run(dr_agui_agent)

    run_finished = [e for e in result if isinstance(e, RunFinishedEvent)]
    assert len(run_finished) == 1
    assert run_finished[0].thread_id == "thread"
    assert run_finished[0].run_id == "run"


class TestPrepareChatCompletionsInput:
    """Tests for DataRobotAGUIAgent._prepare_chat_completions_input (assistant tool_calls and tool messages)."""

    def _input(self, messages: list[Any]) -> Any:
        """Build an input with .messages for _prepare_chat_completions_input."""
        return SimpleNamespace(messages=messages)

    def test_user_message_only(self, dr_agui_agent: DataRobotAGUIAgent) -> None:
        msg = SimpleNamespace(role="user", content="Hello")
        inp = self._input([msg])
        out = dr_agui_agent._prepare_chat_completions_input(inp)
        assert out["messages"] == [{"role": "user", "content": "Hello"}]
        assert out["model"] == "unknown"
        assert out["stream"] is True

    def test_assistant_message_no_tool_calls(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        msg = SimpleNamespace(role="assistant", content="Hi", tool_calls=None)
        inp = self._input([msg])
        out = dr_agui_agent._prepare_chat_completions_input(inp)
        assert out["messages"] == [{"role": "assistant", "content": "Hi"}]

    def test_assistant_message_tool_calls_object_with_valid_id(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        fn = SimpleNamespace(name="my_tool", arguments='{"x":1}')
        tc = SimpleNamespace(id="id-123", function=fn)
        msg = SimpleNamespace(role="assistant", content="", tool_calls=[tc])
        inp = self._input([msg])
        out = dr_agui_agent._prepare_chat_completions_input(inp)
        assert out["messages"] == [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "id-123",
                        "type": "function",
                        "function": {"name": "my_tool", "arguments": '{"x":1}'},
                    }
                ],
            }
        ]

    def test_assistant_tool_call_id_missing_raises(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        tc = {"function": {"name": "f", "arguments": ""}}
        msg = SimpleNamespace(role="assistant", content="", tool_calls=[tc])
        inp = self._input([msg])
        with pytest.raises(ValueError, match="non-empty id"):
            dr_agui_agent._prepare_chat_completions_input(inp)

    def test_assistant_tool_call_id_empty_string_raises(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        tc = {"id": "", "function": {"name": "f", "arguments": ""}}
        msg = SimpleNamespace(role="assistant", content="", tool_calls=[tc])
        inp = self._input([msg])
        with pytest.raises(ValueError, match="non-empty id"):
            dr_agui_agent._prepare_chat_completions_input(inp)

    def test_tool_message_with_tool_call_id(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        msg = SimpleNamespace(
            role="tool", content="result", tool_call_id="call_abc", id=None, error=None
        )
        inp = self._input([msg])
        out = dr_agui_agent._prepare_chat_completions_input(inp)
        assert out["messages"] == [
            {"role": "tool", "content": "result", "tool_call_id": "call_abc"}
        ]

    def test_multi_turn_user_assistant_tool(
        self, dr_agui_agent: DataRobotAGUIAgent
    ) -> None:
        user_msg = SimpleNamespace(role="user", content="Hi")
        tc = {"id": "tc-1", "function": {"name": "n", "arguments": "{}"}}
        asst_msg = SimpleNamespace(role="assistant", content="", tool_calls=[tc])
        tool_msg = SimpleNamespace(
            role="tool", content="done", tool_call_id="tc-1", id=None, error=None
        )
        inp = self._input([user_msg, asst_msg, tool_msg])
        out = dr_agui_agent._prepare_chat_completions_input(inp)
        assert len(out["messages"]) == 3
        assert out["messages"][0] == {"role": "user", "content": "Hi"}
        assert out["messages"][1]["role"] == "assistant"
        assert out["messages"][1]["tool_calls"] == [
            {
                "id": "tc-1",
                "type": "function",
                "function": {"name": "n", "arguments": "{}"},
            }
        ]
        assert out["messages"][2] == {
            "role": "tool",
            "content": "done",
            "tool_call_id": "tc-1",
        }
