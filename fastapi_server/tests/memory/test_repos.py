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

from __future__ import annotations

import uuid as uuidpkg
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.chats import ChatCreate
from app.memory.constants import (
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    thread_session_description,
)
from app.memory.participant import memory_participant_id_context
from app.memory.registry import ChatSessionRegistry
from app.memory.repos import (
    MEMORY_CHAT_MESSAGE_EVENT_TYPE,
    MemoryChatRepository,
    MemoryMessageRepository,
    _emitter_for_message_event,
    memory_space_participant_id,
    memory_space_participant_id_for_user,
    message_to_payload,
    normalize_memory_participant_id,
    payload_to_message,
)
from app.messages import (
    Message,
    MessageCreate,
    MessageReasoning,
    MessageToolCall,
    MessageUpdate,
    Role,
)
from app.users.user import User
from tests.memory.helpers import memory_session


def _user(uid: uuidpkg.UUID) -> User:
    return User(
        id=1,
        uuid=uid,
        email="u@example.com",
        first_name="Te",
        last_name="St",
    )


def test_payload_to_message_rejects_unknown_version() -> None:
    assert payload_to_message({"v": 2, "message_uuid": str(uuidpkg.uuid4())}) is None
    assert payload_to_message(None) is None


def test_message_roundtrip_preserves_fields() -> None:
    chat_id = uuidpkg.uuid4()
    msg_uuid = uuidpkg.uuid4()
    created = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    msg = Message(
        uuid=msg_uuid,
        chat_id=chat_id,
        agui_id="agui-1",
        role=Role.ASSISTANT.value,
        name="bot",
        content="Hello",
        step="s1",
        in_progress=False,
        error=None,
        created_at=created,
        tool_calls=[
            MessageToolCall(
                uuid=uuidpkg.uuid4(),
                message_uuid=msg_uuid,
                agui_id="tc-1",
                tool_call_id="call-1",
                role=Role.TOOL.value,
                name="search",
                arguments='{"q": "x"}',
                content="result",
                in_progress=False,
                created_at=created,
            )
        ],
        reasonings=[
            MessageReasoning(
                uuid=uuidpkg.uuid4(),
                message_uuid=msg_uuid,
                agui_id="rs-1",
                role=Role.REASONING.value,
                name="think",
                content="hmm",
                in_progress=False,
                created_at=created,
            )
        ],
    )

    restored = payload_to_message(message_to_payload(msg))
    assert restored is not None
    assert restored.uuid == msg.uuid
    assert restored.chat_id == chat_id
    assert restored.agui_id == "agui-1"
    assert restored.role == Role.ASSISTANT.value
    assert restored.content == "Hello"
    assert len(restored.tool_calls) == 1
    assert restored.tool_calls[0].name == "search"
    assert restored.tool_calls[0].arguments == '{"q": "x"}'
    assert len(restored.reasonings) == 1
    assert restored.reasonings[0].content == "hmm"


def test_empty_content_uses_wire_placeholder() -> None:
    msg = Message(
        uuid=uuidpkg.uuid4(),
        chat_id=uuidpkg.uuid4(),
        role=Role.USER.value,
        content="",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    payload = message_to_payload(msg)
    assert payload["content"] != ""
    restored = payload_to_message(payload)
    assert restored is not None
    assert restored.content == ""


def test_normalize_memory_participant_id() -> None:
    assert (
        normalize_memory_participant_id("507F1F77BCF86CD799439011")
        == "507f1f77bcf86cd799439011"
    )
    assert normalize_memory_participant_id("not-an-object-id") is None
    assert normalize_memory_participant_id("507f1f77bcf86cd79943901") is None
    assert normalize_memory_participant_id(None) is None


def test_memory_space_participant_id_uses_datarobot_user_id() -> None:
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    dr_user_id = "507f1f77bcf86cd799439011"
    assert (
        memory_space_participant_id(user_uuid, memory_participant_id=dr_user_id)
        == dr_user_id
    )
    assert memory_space_participant_id(user_uuid) != dr_user_id


def test_memory_space_participant_is_24_hex_lowercase() -> None:
    pid = memory_space_participant_id(
        uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    )
    assert len(pid) == 24
    assert pid == pid.lower()
    assert int(pid, 16) >= 0


def test_memory_space_participant_stable_per_user() -> None:
    u = uuidpkg.UUID("87654321-4321-8765-4321-876543218765")
    a = memory_space_participant_id(u)
    b = memory_space_participant_id(u)
    assert a == b


def test_memory_space_participant_differs_between_users() -> None:
    a = memory_space_participant_id(
        uuidpkg.UUID("00000000-0000-4000-8000-000000000001")
    )
    b = memory_space_participant_id(
        uuidpkg.UUID("00000000-0000-4000-8000-000000000002")
    )
    assert a != b


def test_memory_space_participant_id_for_user_matches_uuid_helper() -> None:
    u = _user(uuidpkg.uuid4())
    assert memory_space_participant_id_for_user(u) == memory_space_participant_id(
        u.uuid
    )


@pytest.mark.asyncio
async def test_create_chat_registers_session_with_datarobot_user_id() -> None:
    user_uuid = uuidpkg.uuid4()
    dr_user_id = "507f1f77bcf86cd799439011"
    participant = dr_user_id
    created = memory_session(
        "new-sess",
        thread_id="thread-dr",
        user_uuid=user_uuid,
        name="DR Chat",
        participants=[participant],
    )

    registry = ChatSessionRegistry("space-1")
    repo = MemoryChatRepository("space-1", registry)

    with (
        memory_participant_id_context(dr_user_id),
        patch("app.memory.repos.Session.list", return_value=[]),
        patch("app.memory.repos.Session.create", return_value=created) as create_mock,
    ):
        chat = await repo.create_chat(
            ChatCreate(
                name="DR Chat",
                thread_id="thread-dr",
                user_uuid=user_uuid,
            )
        )

    create_mock.assert_called_once()
    args = create_mock.call_args
    assert args[0][1] == [participant]
    assert chat.user_uuid == user_uuid


@pytest.mark.asyncio
async def test_create_chat_registers_session() -> None:
    user_uuid = uuidpkg.uuid4()
    participant = memory_space_participant_id(user_uuid)
    created = memory_session(
        "new-sess",
        thread_id="thread-1",
        user_uuid=user_uuid,
        name="My Chat",
        participants=[participant],
    )

    registry = ChatSessionRegistry("space-1")
    repo = MemoryChatRepository("space-1", registry)

    with (
        patch("app.memory.repos.Session.list", return_value=[]),
        patch(
            "app.memory.repos.Session.create",
            return_value=created,
        ) as create_mock,
    ):
        chat = await repo.create_chat(
            ChatCreate(name="My Chat", thread_id="thread-1", user_uuid=user_uuid)
        )

    create_mock.assert_called_once()
    args = create_mock.call_args
    assert args[0][0] == "space-1"
    assert args[0][1] == [participant]
    metadata = args[1]["metadata"]
    assert metadata["thread_id"] == "thread-1"
    assert metadata["name"] == "My Chat"
    assert metadata["user_uuid"] == str(user_uuid)
    assert args[1]["description"] == thread_session_description("thread-1")
    assert registry.get_session_id(chat.uuid) == "new-sess"
    assert chat.thread_id == "thread-1"
    assert chat.user_uuid == user_uuid


@pytest.mark.asyncio
async def test_update_chat_name_patches_metadata() -> None:
    user_uuid = uuidpkg.uuid4()
    chat_uuid = uuidpkg.uuid4()
    session = memory_session(
        "sess-1",
        thread_id="t",
        user_uuid=user_uuid,
        chat_uuid=chat_uuid,
        name="Old",
    )
    updated = memory_session(
        "sess-1",
        thread_id="t",
        user_uuid=user_uuid,
        chat_uuid=chat_uuid,
        name="New",
    )

    session.update = MagicMock()
    registry = ChatSessionRegistry("space-1")
    registry.register(chat_uuid, "sess-1")
    repo = MemoryChatRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", side_effect=[session, updated]):
        chat = await repo.update_chat_name(chat_uuid, "New")

    session.update.assert_called_once()
    assert session.update.call_args.kwargs["metadata"]["name"] == "New"
    assert chat is not None
    assert chat.name == "New"
    assert chat.uuid == chat_uuid


@pytest.mark.asyncio
async def test_delete_chat_removes_session_and_unregisters() -> None:
    user_uuid = uuidpkg.uuid4()
    chat_uuid = uuidpkg.uuid4()
    session = memory_session(
        "sess-del",
        thread_id="t",
        user_uuid=user_uuid,
        chat_uuid=chat_uuid,
    )

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_uuid, "sess-del")
    repo = MemoryChatRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", return_value=session):
        deleted = await repo.delete_chat(chat_uuid)

    session.delete.assert_called_once()
    assert deleted is not None
    assert deleted.uuid == chat_uuid
    assert registry.get_session_id(chat_uuid) is None


@pytest.mark.asyncio
async def test_get_chat_by_thread_id_returns_none_when_missing() -> None:
    user_uuid = uuidpkg.uuid4()
    repo = MemoryChatRepository("space-1", ChatSessionRegistry("space-1"))

    with patch("app.memory.repos.Session.list", return_value=[]):
        chat = await repo.get_chat_by_thread_id(user_uuid, "missing")

    assert chat is None


@pytest.mark.asyncio
async def test_get_chat_by_thread_id_lists_by_description() -> None:
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    participant = memory_space_participant_id(user_uuid)
    target_chat = uuidpkg.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    target = memory_session(
        "target-session",
        thread_id="wanted-thread",
        user_uuid=user_uuid,
        chat_uuid=target_chat,
    )

    def fake_list(
        space_id: str,
        *,
        participants: list[str] | None = None,
        description: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[MagicMock]:
        assert space_id == "space-1"
        if description is not None:
            assert participants == [participant]
            assert description == thread_session_description("wanted-thread")
            assert limit == 1
            return [target]
        raise AssertionError("unexpected paginated Session.list call")

    repo = MemoryChatRepository("space-1", ChatSessionRegistry("space-1"))
    with patch(
        "app.memory.repos.Session.list",
        side_effect=fake_list,
    ):
        chat = await repo.get_chat_by_thread_id(user_uuid, "wanted-thread")

    assert chat is not None
    assert chat.uuid == target_chat
    assert chat.thread_id == "wanted-thread"


@pytest.mark.asyncio
async def test_get_chat_by_thread_id_falls_back_to_metadata_scan() -> None:
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    participant = memory_space_participant_id(user_uuid)
    target_chat = uuidpkg.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    target = memory_session(
        "target-session",
        thread_id="wanted-thread",
        user_uuid=user_uuid,
        chat_uuid=target_chat,
    )

    def fake_list(
        space_id: str,
        *,
        participants: list[str] | None = None,
        description: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[MagicMock]:
        assert space_id == "space-1"
        if description is not None:
            return []
        assert participants == [participant]
        assert offset == 0
        return [target]

    repo = MemoryChatRepository("space-1", ChatSessionRegistry("space-1"))
    with patch("app.memory.repos.Session.list", side_effect=fake_list):
        chat = await repo.get_chat_by_thread_id(user_uuid, "wanted-thread")

    assert chat is not None
    assert chat.uuid == target_chat


@pytest.mark.asyncio
async def test_get_all_chats_paginates_for_user() -> None:
    user_uuid = uuidpkg.UUID("87654321-4321-8765-4321-876543218765")
    participant = memory_space_participant_id(user_uuid)
    page1 = [
        memory_session(f"p1-{i}", thread_id=f"t1-{i}", user_uuid=user_uuid)
        for i in range(MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
    ]
    page2 = [
        memory_session(f"p2-{i}", thread_id=f"t2-{i}", user_uuid=user_uuid)
        for i in range(3)
    ]
    list_calls: list[int] = []

    def fake_list(
        space_id: str,
        *,
        offset: int,
        limit: int,
        participants: list[str] | None = None,
    ) -> list[MagicMock]:
        list_calls.append(offset)
        assert participants == [participant]
        if offset == 0:
            return page1[:limit]
        if offset == MEMORY_SPACE_MAX_RETRIEVAL_LIMIT:
            return page2[:limit]
        return []

    repo = MemoryChatRepository("space-1", ChatSessionRegistry("space-1"))
    with patch(
        "app.memory.repos.Session.list",
        side_effect=fake_list,
    ):
        chats = await repo.get_all_chats(_user(user_uuid))

    assert len(chats) == MEMORY_SPACE_MAX_RETRIEVAL_LIMIT + 3
    assert list_calls == [
        0,
        MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
        MEMORY_SPACE_MAX_RETRIEVAL_LIMIT + 3,
    ]


def test_emitter_for_user_message_uses_session_participant() -> None:
    user_pid = memory_space_participant_id(uuidpkg.uuid4())
    session = MagicMock(participants=[user_pid])
    assert _emitter_for_message_event(session, Role.USER.value) == {
        "type": "user",
        "id": user_pid,
    }


def test_emitter_for_agent_message_omits_id() -> None:
    session = MagicMock(participants=["user-participant"])
    assert _emitter_for_message_event(session, Role.ASSISTANT.value) == {
        "type": "agent",
    }


@pytest.mark.asyncio
async def test_create_message_posts_user_event() -> None:
    user_uuid = uuidpkg.uuid4()
    chat_id = uuidpkg.uuid4()
    user_pid = memory_space_participant_id(user_uuid)
    session = MagicMock(participants=[user_pid])
    session.post_event.return_value = MagicMock()

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_id, "sess-1")
    repo = MemoryMessageRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", return_value=session):
        msg = await repo.create_message(
            MessageCreate(chat_id=chat_id, role=Role.USER.value, content="Hi")
        )

    session.post_event.assert_called_once()
    kwargs = session.post_event.call_args.kwargs
    assert kwargs["emitter"] == {"type": "user", "id": user_pid}
    assert kwargs["event_type"] == MEMORY_CHAT_MESSAGE_EVENT_TYPE
    assert kwargs["body"]["content"]
    assert msg.content == "Hi"
    assert msg.chat_id == chat_id


@pytest.mark.asyncio
async def test_create_message_posts_agent_event_without_emitter_id() -> None:
    chat_id = uuidpkg.uuid4()
    session = MagicMock(participants=[memory_space_participant_id(uuidpkg.uuid4())])
    session.post_event.return_value = MagicMock()

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_id, "sess-1")
    repo = MemoryMessageRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", return_value=session):
        await repo.create_message(
            MessageCreate(
                chat_id=chat_id,
                role=Role.ASSISTANT.value,
                content="Reply",
            )
        )

    assert session.post_event.call_args.kwargs["emitter"] == {"type": "agent"}


@pytest.mark.asyncio
async def test_get_chat_messages_orders_by_sequence_id() -> None:
    chat_id = uuidpkg.uuid4()
    msg_uuid = uuidpkg.uuid4()
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = Message(
        uuid=msg_uuid,
        chat_id=chat_id,
        role=Role.USER.value,
        content="first",
        created_at=created,
    )
    second = Message(
        uuid=uuidpkg.uuid4(),
        chat_id=chat_id,
        role=Role.ASSISTANT.value,
        content="second",
        created_at=created,
    )

    def _event(seq: int, msg: Message) -> MagicMock:
        e = MagicMock()
        e.sequence_id = seq
        e.body = message_to_payload(msg)
        return e

    session = MagicMock()
    session.events.side_effect = [
        [_event(2, second), _event(1, first)],
        [],
    ]

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_id, "sess-1")
    repo = MemoryMessageRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", return_value=session):
        messages = await repo.get_chat_messages(chat_id)

    assert [m.content for m in messages] == ["first", "second"]


@pytest.mark.asyncio
async def test_update_message_patches_event_body() -> None:
    chat_id = uuidpkg.uuid4()
    msg_uuid = uuidpkg.uuid4()
    msg = Message(
        uuid=msg_uuid,
        chat_id=chat_id,
        role=Role.USER.value,
        content="before",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    event = MagicMock(sequence_id=7, body=message_to_payload(msg))
    session = MagicMock()
    session.events.side_effect = [[event], []]

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_id, "sess-1")
    repo = MemoryMessageRepository("space-1", registry)
    repo._msg_chat[msg_uuid] = chat_id

    with patch("app.memory.repos.Session.get", return_value=session):
        updated = await repo.update_message(
            msg_uuid, MessageUpdate(content="after", in_progress=False)
        )

    session.update_event.assert_called_once()
    assert session.update_event.call_args[0][0] == 7
    patched_body = session.update_event.call_args.kwargs["body"]
    assert patched_body["content"]
    assert updated is not None
    assert updated.content == "after"
    assert updated.in_progress is False


@pytest.mark.asyncio
async def test_get_message_by_agui_id() -> None:
    chat_id = uuidpkg.uuid4()
    msg = Message(
        uuid=uuidpkg.uuid4(),
        chat_id=chat_id,
        agui_id="agui-find",
        role=Role.USER.value,
        content="find me",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    event = MagicMock(sequence_id=1, body=message_to_payload(msg))
    session = MagicMock()
    session.events.side_effect = [[event], []]

    registry = ChatSessionRegistry("space-1")
    registry.register(chat_id, "sess-1")
    repo = MemoryMessageRepository("space-1", registry)

    with patch("app.memory.repos.Session.get", return_value=session):
        found = await repo.get_message_by_agui_id(chat_id, "agui-find")

    assert found is not None
    assert found.content == "find me"
