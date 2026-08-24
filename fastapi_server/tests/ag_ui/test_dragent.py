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
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator, Callable, Dict, Iterator, List

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
    ToolCallEndEvent,
    ToolCallStartEvent,
)

from app.ag_ui.dragent import DRAgentAGUIAgent, DRAgentEventResponse
from app.config import Config
from tests.ag_ui.conftest import run_input

_TEST_AGENT_NAME = "Test DRAgent Agent"


@pytest.fixture
def dragent_agui_agent(config: Config) -> Iterator[DRAgentAGUIAgent]:
    yield DRAgentAGUIAgent(_TEST_AGENT_NAME, config)


@pytest.fixture
def dragent_agui_agent_heartbeat(config: Config) -> Iterator[DRAgentAGUIAgent]:
    yield DRAgentAGUIAgent(
        _TEST_AGENT_NAME, config, heartbeat_interval=0.1, check_interval=0.02
    )


async def run(agent: DRAgentAGUIAgent, *messages: Message) -> list[BaseEvent]:
    result = []
    async for event in agent.run(run_input(*messages)):
        result.append(event)
    return result


class MockSSE:
    def __init__(self, data: str) -> None:
        self.data = data


class MockResponse:
    def __init__(self, status_code: int = 200, body: bytes = b"") -> None:
        self.status_code = status_code
        self._body = body

    async def aread(self) -> bytes:
        return self._body


class MockEventSource:
    def __init__(self, sse_items: List[MockSSE], status_code: int = 200) -> None:
        self._items = sse_items
        self.response = MockResponse(status_code=status_code)

    async def aiter_sse(self) -> AsyncIterator[MockSSE]:
        for item in self._items:
            yield item


class MockSlowEventSource:
    def __init__(self, sse_items: List[MockSSE], delay: float = 0.1) -> None:
        self._items = sse_items
        self._delay = delay
        self.response = MockResponse()

    async def aiter_sse(self) -> AsyncIterator[MockSSE]:
        for item in self._items:
            await asyncio.sleep(self._delay)
            yield item


def make_sse(events: List[BaseEvent]) -> MockSSE:
    response = DRAgentEventResponse(events=events)
    return MockSSE(data=response.model_dump_json())


@pytest.fixture
def set_sse_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[List[MockSSE], int], None]:
    """Fixture that patches httpx_sse.aconnect_sse to yield given SSE items."""
    sse_items: List[MockSSE] = []
    status_code_ref = [200]

    @asynccontextmanager
    async def mock_aconnect_sse(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[MockEventSource, None]:
        yield MockEventSource(sse_items, status_code=status_code_ref[0])

    monkeypatch.setattr("httpx_sse.aconnect_sse", mock_aconnect_sse)

    def set(items: List[MockSSE], status_code: int = 200) -> None:
        sse_items.clear()
        sse_items.extend(items)
        status_code_ref[0] = status_code

    return set


@pytest.fixture
def set_sse_responses_slow(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[List[MockSSE]], None]:
    """Fixture that patches httpx_sse.aconnect_sse to yield SSE items with a delay."""
    sse_items: List[MockSSE] = []

    @asynccontextmanager
    async def mock_aconnect_sse(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[MockSlowEventSource, None]:
        yield MockSlowEventSource(sse_items)

    monkeypatch.setattr("httpx_sse.aconnect_sse", mock_aconnect_sse)

    def set(items: List[MockSSE]) -> None:
        sse_items.clear()
        sse_items.extend(items)

    return set


@pytest.fixture
def error_sse(monkeypatch: pytest.MonkeyPatch) -> Callable[[BaseException], None]:
    """Fixture that patches httpx_sse.aconnect_sse to raise an exception."""
    exception: List[BaseException] = []

    @asynccontextmanager
    async def mock_aconnect_sse(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[None, None]:
        raise exception[0]
        yield  # make it an async generator

    monkeypatch.setattr("httpx_sse.aconnect_sse", mock_aconnect_sse)

    def set(e: BaseException) -> None:
        exception.append(e)

    return set


async def test_run_single_message(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    msg_id = "msg-1"
    set_sse_responses(
        [
            make_sse(
                [
                    TextMessageStartEvent(message_id=msg_id),
                    TextMessageContentEvent(message_id=msg_id, delta="Hello!"),
                    TextMessageEndEvent(message_id=msg_id),
                    RunFinishedEvent(thread_id="thread", run_id="run"),
                ]
            )
        ]
    )
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        TextMessageStartEvent(message_id=msg_id),
        TextMessageContentEvent(message_id=msg_id, delta="Hello!"),
        TextMessageEndEvent(message_id=msg_id),
        RunFinishedEvent(thread_id="thread", run_id="run"),
    ]


async def test_run_with_tool_calls(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    msg_id = "msg-1"
    tool_call_id = "tc-1"
    set_sse_responses(
        [
            make_sse(
                [
                    TextMessageStartEvent(message_id=msg_id),
                    ToolCallStartEvent(
                        tool_call_id=tool_call_id,
                        tool_call_name="my_tool",
                        parent_message_id=msg_id,
                    ),
                    ToolCallEndEvent(tool_call_id=tool_call_id),
                    TextMessageEndEvent(message_id=msg_id),
                    RunFinishedEvent(thread_id="thread", run_id="run"),
                ]
            )
        ]
    )
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        TextMessageStartEvent(message_id=msg_id),
        ToolCallStartEvent(
            tool_call_id=tool_call_id,
            tool_call_name="my_tool",
            parent_message_id=msg_id,
        ),
        ToolCallEndEvent(tool_call_id=tool_call_id),
        TextMessageEndEvent(message_id=msg_id),
        RunFinishedEvent(thread_id="thread", run_id="run"),
    ]


async def test_run_error(
    error_sse: Callable[[BaseException], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    error_sse(RuntimeError("connection failed"))
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        RunErrorEvent(message="connection failed", thread_id="thread", run_id="run"),
    ]


async def test_run_http_error_status(
    set_sse_responses: Callable[[List[MockSSE], int], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    set_sse_responses([], 503)
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        RunErrorEvent(
            message="DRAgent server returned error 503: ",
            thread_id="thread",
            run_id="run",
        ),
    ]


async def test_run_empty_response(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    set_sse_responses([])
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        RunErrorEvent(
            message="No events received from the DRAgent server. Please check if the server is running.",
            thread_id="thread",
            run_id="run",
        ),
    ]


async def test_run_filters_dragent_run_started_and_finished_events(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """DRAgent server's RunStartedEvent/RunFinishedEvent must be suppressed; only our wrapper's should appear."""
    msg_id = "msg-1"
    set_sse_responses(
        [
            make_sse(
                [
                    RunStartedEvent(thread_id="", run_id=""),
                    TextMessageStartEvent(message_id=msg_id),
                    TextMessageContentEvent(message_id=msg_id, delta="Hi"),
                    TextMessageEndEvent(message_id=msg_id),
                    RunFinishedEvent(thread_id="", run_id=""),
                ]
            )
        ]
    )
    result = await run(dragent_agui_agent)
    # Exactly one RunStartedEvent and one RunFinishedEvent — our wrapper's
    assert result.count(RunStartedEvent(thread_id="thread", run_id="run")) == 1
    assert result.count(RunFinishedEvent(thread_id="thread", run_id="run")) == 1
    # No stray RunStarted/RunFinished with empty IDs
    assert RunStartedEvent(thread_id="", run_id="") not in result
    assert RunFinishedEvent(thread_id="", run_id="") not in result


async def test_run_stops_after_forwarded_run_error_event(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """A RunErrorEvent forwarded from the DRAgent server must terminate the run.

    AG-UI allows exactly one terminal event per run, so no RunFinishedEvent (nor
    any later event) may follow it.
    """
    msg_id = "msg-1"
    set_sse_responses(
        [
            make_sse(
                [
                    TextMessageStartEvent(message_id=msg_id),
                    TextMessageContentEvent(message_id=msg_id, delta="Hi"),
                    TextMessageEndEvent(message_id=msg_id),
                    RunErrorEvent(message="Model name is required"),
                ]
            ),
            make_sse([CustomEvent(name="after-error", value={})]),
        ]
    )
    result = await run(dragent_agui_agent)
    assert result[-1] == RunErrorEvent(message="Model name is required")
    assert not [e for e in result if isinstance(e, RunFinishedEvent)]
    assert len([e for e in result if isinstance(e, RunErrorEvent)]) == 1
    assert not [e for e in result if isinstance(e, CustomEvent)]


async def test_run_skips_empty_sse_data(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """SSE frames with empty data must be skipped without error."""
    msg_id = "msg-1"
    set_sse_responses(
        [
            MockSSE(data=""),
            make_sse(
                [
                    TextMessageStartEvent(message_id=msg_id),
                    TextMessageContentEvent(message_id=msg_id, delta="Hi"),
                    TextMessageEndEvent(message_id=msg_id),
                ]
            ),
        ]
    )
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        TextMessageStartEvent(message_id=msg_id),
        TextMessageContentEvent(message_id=msg_id, delta="Hi"),
        TextMessageEndEvent(message_id=msg_id),
        RunFinishedEvent(thread_id="thread", run_id="run"),
    ]


async def test_run_skips_sse_frame_with_no_events(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """SSE frames with an empty or missing events list must not count as received events."""
    msg_id = "msg-1"
    set_sse_responses(
        [
            MockSSE(data='{"events": []}'),
            MockSSE(data="{}"),
            make_sse(
                [
                    TextMessageStartEvent(message_id=msg_id),
                    TextMessageContentEvent(message_id=msg_id, delta="Hi"),
                    TextMessageEndEvent(message_id=msg_id),
                ]
            ),
        ]
    )
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        TextMessageStartEvent(message_id=msg_id),
        TextMessageContentEvent(message_id=msg_id, delta="Hi"),
        TextMessageEndEvent(message_id=msg_id),
        RunFinishedEvent(thread_id="thread", run_id="run"),
    ]


async def test_run_empty_response_only_empty_frames(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """If all SSE frames have empty data/events, the agent should still raise a no-events error."""
    set_sse_responses([MockSSE(data=""), MockSSE(data='{"events": []}')])
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        RunErrorEvent(
            message="No events received from the DRAgent server. Please check if the server is running.",
            thread_id="thread",
            run_id="run",
        ),
    ]


async def test_run_strips_none_fields_in_events(
    set_sse_responses: Callable[[List[MockSSE]], None],
    dragent_agui_agent: DRAgentAGUIAgent,
) -> None:
    """Events with null fields in the SSE payload must parse without validation errors."""
    msg_id = "msg-1"
    # Manually craft a payload with null fields that _strip_none should remove
    raw_payload = (
        '{"events": ['
        '{"type": "TEXT_MESSAGE_START", "message_id": "' + msg_id + '", "role": null},'
        '{"type": "TEXT_MESSAGE_CONTENT", "message_id": "'
        + msg_id
        + '", "delta": "Hi", "extra": null},'
        '{"type": "TEXT_MESSAGE_END", "message_id": "' + msg_id + '"}'
        "]}"
    )
    set_sse_responses([MockSSE(data=raw_payload)])
    result = await run(dragent_agui_agent)
    assert result == [
        RunStartedEvent(thread_id="thread", run_id="run"),
        TextMessageStartEvent(message_id=msg_id),
        TextMessageContentEvent(message_id=msg_id, delta="Hi"),
        TextMessageEndEvent(message_id=msg_id),
        RunFinishedEvent(thread_id="thread", run_id="run"),
    ]


async def test_run_custom_headers_are_sent(
    monkeypatch: pytest.MonkeyPatch,
    config: Config,
) -> None:
    """Custom headers passed to the constructor must be included in the request."""
    captured_headers: Dict[str, str] = {}

    @asynccontextmanager
    async def mock_aconnect_sse(
        client: object,
        method: object,
        url: object,
        headers: Dict[str, str],
        **kwargs: object,
    ) -> AsyncGenerator[MockEventSource, None]:
        captured_headers.update(headers)
        msg_id = "msg-1"
        yield MockEventSource(
            [
                make_sse(
                    [
                        TextMessageStartEvent(message_id=msg_id),
                        TextMessageEndEvent(message_id=msg_id),
                    ]
                )
            ],
            status_code=200,
        )

    monkeypatch.setattr("httpx_sse.aconnect_sse", mock_aconnect_sse)

    agent = DRAgentAGUIAgent(
        _TEST_AGENT_NAME, config, headers={"X-Custom-Header": "my-value"}
    )
    await run(agent)

    assert captured_headers.get("X-Custom-Header") == "my-value"
    assert "Authorization" in captured_headers


async def test_run_heartbeat(
    set_sse_responses_slow: Callable[[List[MockSSE]], None],
    dragent_agui_agent_heartbeat: DRAgentAGUIAgent,
) -> None:
    msg_id = "msg-1"
    set_sse_responses_slow(
        [
            make_sse([TextMessageStartEvent(message_id=msg_id)]),
            make_sse(
                [
                    TextMessageContentEvent(message_id=msg_id, delta="Hi"),
                    TextMessageEndEvent(message_id=msg_id),
                    RunFinishedEvent(thread_id="thread", run_id="run"),
                ]
            ),
        ]
    )
    result = await run(dragent_agui_agent_heartbeat)
    assert RunStartedEvent(thread_id="thread", run_id="run") in result
    assert (
        CustomEvent(name="Heartbeat", value={"thread_id": "thread", "run_id": "run"})
        in result
    )
    assert RunFinishedEvent(thread_id="thread", run_id="run") in result
