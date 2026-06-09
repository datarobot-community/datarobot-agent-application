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

import asyncio
import hashlib
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from datarobot.models.memory import Event, Session

from app.chats import Chat, ChatCreate
from app.memory.constants import (
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    thread_session_description,
)
from app.memory.locks import memory_space_lock
from app.memory.metadata_keys import session_metadata
from app.memory.participant import (
    get_memory_participant_id,
    normalize_memory_participant_id,
)
from app.memory.registry import ChatSessionRegistry
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
from app.users.user import User

logger = logging.getLogger(__name__)

# Memory-service list APIs only accept message | tool_output | status (see eventType query).
# New events are stored as "message"; older sessions may use other type labels but the same body schema.
MEMORY_CHAT_MESSAGE_EVENT_TYPE = "message"

# Memory-service event bodies reject empty strings on some fields (min_length=1).
# We use an invisible placeholder on the wire and strip it when hydrating models.
_MEMORY_MIN_LENGTH_PLACEHOLDER = "\u200b"


def _wire_non_empty_str(value: str | None) -> str:
    s = value or ""
    return s if s else _MEMORY_MIN_LENGTH_PLACEHOLDER


def _app_str(value: str | None) -> str:
    s = value or ""
    return "" if s == _MEMORY_MIN_LENGTH_PLACEHOLDER else s


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def message_to_payload(msg: Message) -> dict[str, Any]:
    return {
        "v": 1,
        "message_uuid": str(msg.uuid),
        "chat_id": str(msg.chat_id) if msg.chat_id else None,
        "agui_id": msg.agui_id,
        "role": msg.role,
        "name": msg.name or "",
        "content": _wire_non_empty_str(msg.content),
        "step": msg.step,
        "in_progress": msg.in_progress,
        "error": msg.error,
        "created_at": msg.created_at.isoformat(),
        "tool_calls": [tool_call_to_payload(tc) for tc in msg.tool_calls],
        "reasonings": [reasoning_to_payload(r) for r in msg.reasonings],
    }


def tool_call_to_payload(tc: MessageToolCall) -> dict[str, Any]:
    return {
        "uuid": str(tc.uuid),
        "agui_id": tc.agui_id,
        "tool_call_id": tc.tool_call_id,
        "role": tc.role,
        "name": tc.name or "",
        "arguments": _wire_non_empty_str(tc.arguments),
        "content": _wire_non_empty_str(tc.content),
        "in_progress": tc.in_progress,
        "error": tc.error,
        "created_at": tc.created_at.isoformat(),
    }


def reasoning_to_payload(r: MessageReasoning) -> dict[str, Any]:
    return {
        "uuid": str(r.uuid),
        "agui_id": r.agui_id,
        "role": r.role,
        "name": r.name or "",
        "content": _wire_non_empty_str(r.content),
        "in_progress": r.in_progress,
        "error": r.error,
        "created_at": r.created_at.isoformat(),
    }


def payload_to_message(body: dict[str, Any] | None) -> Message | None:
    if not body or body.get("v") != 1:
        return None
    tool_calls = [
        MessageToolCall(
            uuid=UUID(d["uuid"]),
            message_uuid=UUID(body["message_uuid"]),
            tool_call_id=d.get("tool_call_id"),
            agui_id=d.get("agui_id"),
            role=d.get("role", "tool"),
            name=d.get("name") or "",
            arguments=_app_str(d.get("arguments")),
            content=_app_str(d.get("content")),
            in_progress=d.get("in_progress", True),
            error=d.get("error"),
            created_at=_parse_dt(d.get("created_at")),
        )
        for d in body.get("tool_calls") or []
    ]
    reasonings = [
        MessageReasoning(
            uuid=UUID(d["uuid"]),
            message_uuid=UUID(body["message_uuid"]),
            agui_id=d.get("agui_id"),
            role=d.get("role", "reasoning"),
            name=d.get("name") or "",
            content=_app_str(d.get("content")),
            in_progress=d.get("in_progress", True),
            error=d.get("error"),
            created_at=_parse_dt(d.get("created_at")),
        )
        for d in body.get("reasonings") or []
    ]
    cid_raw = body.get("chat_id")
    return Message(
        uuid=UUID(body["message_uuid"]),
        chat_id=UUID(cid_raw) if cid_raw else None,
        agui_id=body.get("agui_id"),
        role=body.get("role", "user"),
        name=body.get("name") or "",
        content=_app_str(body.get("content")),
        step=body.get("step"),
        in_progress=body.get("in_progress", True),
        error=body.get("error"),
        created_at=_parse_dt(body.get("created_at")),
        tool_calls=tool_calls,
        reasonings=reasonings,
    )


_MEMORY_PARTICIPANT_ID_LEN = 24


def memory_space_participant_id(
    user_uuid: UUID,
    *,
    memory_participant_id: str | None = None,
) -> str:
    """
    Stable memory-service participant id: 24 hex chars (BSON ObjectId length).

    Uses an explicit ``memory_participant_id``, else the value bound for the
    current request (``X-DataRobot-User-Id`` via :class:`MemoryParticipantMiddleware`),
    else a deterministic ObjectId-shaped value from ``user_uuid``.
    """
    raw = memory_participant_id
    if raw is None:
        raw = get_memory_participant_id()
    if normalized := normalize_memory_participant_id(raw):
        return normalized
    return hashlib.sha256(user_uuid.bytes).hexdigest()[:_MEMORY_PARTICIPANT_ID_LEN]


def memory_space_participant_id_for_user(
    user: User,
    *,
    memory_participant_id: str | None = None,
) -> str:
    return memory_space_participant_id(
        user.uuid, memory_participant_id=memory_participant_id
    )


def _emitter_for_message_event(session: Session, message_role: str) -> dict[str, str]:
    """Build memory-service event emitter (type user|agent, id = 24-hex ObjectId).

    Sessions are created with a single ``participants`` entry (the app user). The
    memory API does not allow a second session participant for the agent, so
    assistant events use :data:`MEMORY_APP_AGENT_PARTICIPANT_ID` as emitter id.
    """
    parts = list(session.participants or [])
    user_pid = parts[0] if parts else None
    if message_role == Role.USER.value:
        if not user_pid:
            raise ValueError("Memory session has no user participant for event emitter")
        return {"type": "user", "id": user_pid}
    return {"type": "agent"}


def _memory_session_get(memory_space_id: str, session_id: str) -> Session:
    return Session.get(memory_space_id, session_id)


def _fetch_last_message_events(space_id: str, session_id: str) -> list[Event]:
    """Return the chat message event with the highest sequence_id among recent session events."""
    session = Session.get(space_id, session_id)
    recent = session.events(last_n=MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
    ours = [e for e in recent if e.body and payload_to_message(e.body) is not None]
    if not ours:
        return []
    best = max(ours, key=lambda e: e.sequence_id or 0)
    return [best]


class MemoryChatRepository:
    """Chat persistence backed by DataRobot memory-service sessions."""

    def __init__(self, memory_space_id: str, registry: ChatSessionRegistry) -> None:
        self._memory_space_id = memory_space_id
        self._registry = registry

    async def _iter_sessions(
        self,
        *,
        participants: list[str] | None = None,
    ) -> AsyncIterator[Session]:
        """Yield every session in the memory space, paginating past the list API page size."""
        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_page(o: int, lim: int, p: list[str] | None) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                if p is not None:
                    return Session.list(
                        self._memory_space_id,
                        offset=o,
                        limit=capped,
                        participants=p,
                    )
                return Session.list(
                    self._memory_space_id,
                    offset=o,
                    limit=capped,
                )

            batch = await asyncio.to_thread(_list_page, offset, page_size, participants)
            if not batch:
                break
            for s in batch:
                yield s
            offset += len(batch)

    def _session_to_chat(self, session: Session) -> Chat:
        sid = session.id
        if sid is None:
            raise ValueError("Memory session is missing id")
        md = session_metadata(session)
        raw_chat = md.get("chat_uuid")
        if not raw_chat:
            raise ValueError("Memory session is missing chat_uuid metadata")
        chat_uuid = UUID(raw_chat)
        self._registry.register(chat_uuid, sid)
        uu = md.get("user_uuid")
        return Chat(
            uuid=chat_uuid,
            name=md.get("name", "New Chat"),
            thread_id=md.get("thread_id"),
            user_uuid=UUID(uu) if uu else None,
            created_at=session.created_at,
        )

    async def create_chat(self, chat_data: ChatCreate) -> Chat:
        if chat_data.user_uuid is None:
            raise ValueError(
                "user_uuid is required when storing chats in memory service"
            )
        if chat_data.thread_id is None:
            raise ValueError(
                "thread_id is required when storing chats in memory service"
            )

        lock_key = (
            f"{self._memory_space_id}:chat:{chat_data.user_uuid}:{chat_data.thread_id}"
        )
        async with memory_space_lock(lock_key):
            existing = await self.get_chat_by_thread_id(
                chat_data.user_uuid, chat_data.thread_id
            )
            if existing is not None:
                return existing

            chat_uuid = uuid4()
            metadata = {
                "thread_id": chat_data.thread_id,
                "name": chat_data.name,
                "chat_uuid": str(chat_uuid),
                "user_uuid": str(chat_data.user_uuid),
            }
            # Memory-service validates max_length=1 on participants for this deployment.
            participants = [memory_space_participant_id(chat_data.user_uuid)]

            description = thread_session_description(chat_data.thread_id)

            def _create() -> Session:
                return Session.create(
                    self._memory_space_id,
                    participants,
                    metadata=metadata,
                    description=description,
                )

            session = await asyncio.to_thread(_create)
            created_id = session.id
            if created_id is None:
                raise ValueError("Memory service returned a session without id")
            self._registry.register(chat_uuid, created_id)
            return Chat(
                uuid=chat_uuid,
                name=chat_data.name,
                thread_id=chat_data.thread_id,
                user_uuid=chat_data.user_uuid,
                created_at=session.created_at,
            )

    async def get_chat_by_thread_id(
        self,
        user_uuid: UUID,
        thread_id: str,
    ) -> Chat | None:
        participant = memory_space_participant_id(user_uuid)
        description = thread_session_description(thread_id)

        def _list_by_thread() -> list[Session]:
            return Session.list(
                self._memory_space_id,
                participants=[participant],
                description=description,
                limit=1,
            )

        batch = await asyncio.to_thread(_list_by_thread)
        if batch:
            s = batch[0]
            md = session_metadata(s)
            if md.get("thread_id") == thread_id and md.get("user_uuid") == str(
                user_uuid
            ):
                return self._session_to_chat(s)

        async for s in self._iter_sessions(participants=[participant]):
            md = session_metadata(s)
            if md.get("thread_id") == thread_id and md.get("user_uuid") == str(
                user_uuid
            ):
                return self._session_to_chat(s)
        return None

    async def get_all_chats(self, user: User | None) -> Sequence[Chat]:
        participants: list[str] | None
        if user:
            participants = [memory_space_participant_id_for_user(user)]
        else:
            participants = None
        result: list[Chat] = []
        async for s in self._iter_sessions(participants=participants):
            try:
                result.append(self._session_to_chat(s))
            except ValueError:
                logger.warning("Skipping memory session %s with invalid metadata", s.id)
        return result

    async def update_chat_name(self, chat_uuid: UUID, name: str) -> Chat | None:
        sid = await self._registry.resolve_session_id(chat_uuid)
        if not sid:
            return None

        def _patch() -> Session:
            s = Session.get(self._memory_space_id, sid)
            md = dict(session_metadata(s))
            md["name"] = name
            s.update(metadata=md)
            return Session.get(self._memory_space_id, sid)

        session = await asyncio.to_thread(_patch)
        return self._session_to_chat(session)

    async def delete_chat(self, chat_uuid: UUID) -> Chat | None:
        sid = await self._registry.resolve_session_id(chat_uuid)
        if not sid:
            return None

        def _delete() -> Chat:
            s = Session.get(self._memory_space_id, sid)
            md = session_metadata(s)
            chat = Chat(
                uuid=UUID(md["chat_uuid"]),
                name=md.get("name", "New Chat"),
                thread_id=md.get("thread_id"),
                user_uuid=UUID(md["user_uuid"]) if md.get("user_uuid") else None,
                created_at=s.created_at,
            )
            s.delete()
            return chat

        chat = await asyncio.to_thread(_delete)
        self._registry.unregister(chat_uuid)
        return chat


class MemoryMessageRepository:
    """Message persistence backed by memory-service session events (one event per message)."""

    def __init__(self, memory_space_id: str, registry: ChatSessionRegistry) -> None:
        self._memory_space_id = memory_space_id
        self._registry = registry
        self._msg_chat: dict[UUID, UUID] = {}
        self._tc_chat: dict[UUID, UUID] = {}
        self._rs_chat: dict[UUID, UUID] = {}
        self._tool_call_message: dict[UUID, UUID] = {}
        self._reasoning_message: dict[UUID, UUID] = {}

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        """No-op batching scope; memory-service calls have no shared transaction."""
        yield

    def _remember_maps(self, msg: Message, chat_id: UUID) -> None:
        self._msg_chat[msg.uuid] = chat_id
        for tc in msg.tool_calls:
            self._tc_chat[tc.uuid] = chat_id
            self._tool_call_message[tc.uuid] = msg.uuid
        for r in msg.reasonings:
            self._rs_chat[r.uuid] = chat_id
            self._reasoning_message[r.uuid] = msg.uuid

    async def _session_for_chat(self, chat_id: UUID) -> Session:
        sid = await self._registry.resolve_session_id(chat_id)
        if not sid:
            raise ValueError(f"No memory session for chat_id={chat_id}")
        return await asyncio.to_thread(_memory_session_get, self._memory_space_id, sid)

    async def _iter_message_events(self, session: Session) -> list[Event]:
        out: list[Event] = []
        offset = 0
        page = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _events_page(sess: Session, o: int, lim: int) -> list[Event]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return sess.events(offset=o, limit=capped)

            batch = await asyncio.to_thread(_events_page, session, offset, page)
            if not batch:
                break
            for e in batch:
                if e.body and payload_to_message(e.body) is not None:
                    out.append(e)
            offset += len(batch)
        return out

    async def _find_event_for_message_uuid(
        self, session: Session, message_uuid: UUID
    ) -> Event | None:
        for e in await self._iter_message_events(session):
            if e.body and e.body.get("message_uuid") == str(message_uuid):
                return e
        return None

    async def _discover_chat_for_message(self, message_uuid: UUID) -> UUID | None:
        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_batch(o: int, lim: int) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return Session.list(self._memory_space_id, offset=o, limit=capped)

            batch = await asyncio.to_thread(_list_batch, offset, page_size)
            if not batch:
                return None
            for s in batch:
                sid = s.id
                if sid is None:
                    continue

                session = await asyncio.to_thread(
                    _memory_session_get, self._memory_space_id, sid
                )
                ev = await self._find_event_for_message_uuid(session, message_uuid)
                if ev and ev.body:
                    raw = ev.body.get("chat_id")
                    if raw:
                        chat_id = UUID(raw)
                        self._registry.register(chat_id, sid)
                        return chat_id
            offset += len(batch)

    async def create_message(self, message_data: MessageCreate) -> Message:
        if message_data.chat_id is None:
            raise ValueError("chat_id is required")

        msg = Message(**message_data.model_dump(), uuid=uuid4())
        msg.tool_calls = []
        msg.reasonings = []

        session = await self._session_for_chat(message_data.chat_id)
        emitter = _emitter_for_message_event(session, msg.role)

        def _post() -> Event:
            return session.post_event(
                body=message_to_payload(msg),
                emitter=emitter,
                event_type=MEMORY_CHAT_MESSAGE_EVENT_TYPE,
            )

        await asyncio.to_thread(_post)
        self._remember_maps(msg, message_data.chat_id)
        return msg

    async def update_message(self, uuid: UUID, update: MessageUpdate) -> Message | None:
        chat_id = self._msg_chat.get(uuid)
        if chat_id is None:
            discovered = await self._discover_chat_for_message(uuid)
            if discovered is None:
                return None
            chat_id = discovered

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(session, uuid)
        if not ev or ev.sequence_id is None or not ev.body:
            return None

        msg = payload_to_message(ev.body)
        if not msg:
            return None
        for field, value in update.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(msg, field, value)

        seq = ev.sequence_id

        def _patch() -> None:
            session.update_event(seq, body=message_to_payload(msg))

        await asyncio.to_thread(_patch)
        self._remember_maps(msg, chat_id)
        return msg

    async def create_message_tool_call(
        self, message_tool_call_data: MessageToolCallCreate
    ) -> MessageToolCall:
        chat_id = self._msg_chat.get(message_tool_call_data.message_uuid)
        if chat_id is None:
            discovered = await self._discover_chat_for_message(
                message_tool_call_data.message_uuid
            )
            if discovered is None:
                raise ValueError(
                    f"Message {message_tool_call_data.message_uuid} does not exist"
                )
            chat_id = discovered

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(
            session, message_tool_call_data.message_uuid
        )
        if not ev or ev.sequence_id is None or not ev.body:
            raise ValueError(
                f"Message {message_tool_call_data.message_uuid} does not exist"
            )

        msg = payload_to_message(ev.body)
        if not msg:
            raise ValueError(
                f"Message {message_tool_call_data.message_uuid} does not exist"
            )

        tc = MessageToolCall(**message_tool_call_data.model_dump(), uuid=uuid4())
        msg.tool_calls = [*msg.tool_calls, tc]

        seq = ev.sequence_id

        def _patch() -> None:
            session.update_event(seq, body=message_to_payload(msg))

        await asyncio.to_thread(_patch)
        self._remember_maps(msg, chat_id)
        return tc

    async def update_message_tool_call(
        self, uuid: UUID, update: MessageToolCallUpdate
    ) -> MessageToolCall | None:
        msg_uuid = self._tool_call_message.get(uuid)
        chat_id = self._tc_chat.get(uuid)
        if msg_uuid is None or chat_id is None:
            found = await self._discover_tool_call(uuid)
            if found is None:
                return None
            msg_uuid, chat_id = found

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(session, msg_uuid)
        if not ev or ev.sequence_id is None or not ev.body:
            return None

        msg = payload_to_message(ev.body)
        if not msg:
            return None

        updated_tc: MessageToolCall | None = None
        new_tool_calls: list[MessageToolCall] = []
        for tc in msg.tool_calls:
            if tc.uuid == uuid:
                for field, value in update.model_dump(exclude_unset=True).items():
                    if value is not None:
                        setattr(tc, field, value)
                updated_tc = tc
            new_tool_calls.append(tc)

        if updated_tc is None:
            return None

        msg.tool_calls = new_tool_calls
        seq = ev.sequence_id

        def _patch() -> None:
            session.update_event(seq, body=message_to_payload(msg))

        await asyncio.to_thread(_patch)
        self._remember_maps(msg, chat_id)
        return updated_tc

    async def _discover_tool_call(
        self, tool_call_uuid: UUID
    ) -> tuple[UUID, UUID] | None:
        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_batch(o: int, lim: int) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return Session.list(self._memory_space_id, offset=o, limit=capped)

            batch = await asyncio.to_thread(_list_batch, offset, page_size)
            if not batch:
                return None
            for s in batch:
                sid = s.id
                if sid is None:
                    continue
                session = await asyncio.to_thread(
                    _memory_session_get, self._memory_space_id, sid
                )
                for e in await self._iter_message_events(session):
                    msg = payload_to_message(e.body or {})
                    if msg and any(tc.uuid == tool_call_uuid for tc in msg.tool_calls):
                        assert msg.chat_id is not None
                        self._registry.register(msg.chat_id, sid)
                        return msg.uuid, msg.chat_id
            offset += len(batch)

    async def create_message_reasoning(
        self, message_reasoning_data: MessageReasoningCreate
    ) -> MessageReasoning:
        chat_id = self._msg_chat.get(message_reasoning_data.message_uuid)
        if chat_id is None:
            discovered = await self._discover_chat_for_message(
                message_reasoning_data.message_uuid
            )
            if discovered is None:
                raise ValueError(
                    f"Message {message_reasoning_data.message_uuid} does not exist"
                )
            chat_id = discovered

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(
            session, message_reasoning_data.message_uuid
        )
        if not ev or ev.sequence_id is None or not ev.body:
            raise ValueError(
                f"Message {message_reasoning_data.message_uuid} does not exist"
            )

        msg = payload_to_message(ev.body)
        if not msg:
            raise ValueError(
                f"Message {message_reasoning_data.message_uuid} does not exist"
            )

        reasoning = MessageReasoning(
            **message_reasoning_data.model_dump(), uuid=uuid4()
        )
        msg.reasonings = [*msg.reasonings, reasoning]

        seq = ev.sequence_id

        def _patch() -> None:
            session.update_event(seq, body=message_to_payload(msg))

        await asyncio.to_thread(_patch)
        self._remember_maps(msg, chat_id)
        return reasoning

    async def update_message_reasoning(
        self, uuid: UUID, update: MessageReasoningUpdate
    ) -> MessageReasoning | None:
        msg_uuid = self._reasoning_message.get(uuid)
        chat_id = self._rs_chat.get(uuid)
        if msg_uuid is None or chat_id is None:
            found = await self._discover_reasoning(uuid)
            if found is None:
                return None
            msg_uuid, chat_id = found

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(session, msg_uuid)
        if not ev or ev.sequence_id is None or not ev.body:
            return None

        msg = payload_to_message(ev.body)
        if not msg:
            return None

        updated: MessageReasoning | None = None
        new_reasonings: list[MessageReasoning] = []
        for r in msg.reasonings:
            if r.uuid == uuid:
                for field, value in update.model_dump(exclude_unset=True).items():
                    if value is not None:
                        setattr(r, field, value)
                updated = r
            new_reasonings.append(r)

        if updated is None:
            return None

        msg.reasonings = new_reasonings
        seq = ev.sequence_id

        def _patch() -> None:
            session.update_event(seq, body=message_to_payload(msg))

        await asyncio.to_thread(_patch)
        self._remember_maps(msg, chat_id)
        return updated

    async def _discover_reasoning(
        self, reasoning_uuid: UUID
    ) -> tuple[UUID, UUID] | None:
        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_batch(o: int, lim: int) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return Session.list(self._memory_space_id, offset=o, limit=capped)

            batch = await asyncio.to_thread(_list_batch, offset, page_size)
            if not batch:
                return None
            for s in batch:
                sid = s.id
                if sid is None:
                    continue
                session = await asyncio.to_thread(
                    _memory_session_get, self._memory_space_id, sid
                )
                for e in await self._iter_message_events(session):
                    msg = payload_to_message(e.body or {})
                    if msg and any(r.uuid == reasoning_uuid for r in msg.reasonings):
                        assert msg.chat_id is not None
                        self._registry.register(msg.chat_id, sid)
                        return msg.uuid, msg.chat_id
            offset += len(batch)

    async def get_message_by_agui_id(
        self, chat_id: UUID, agui_id: str
    ) -> Message | None:
        session = await self._session_for_chat(chat_id)
        for e in await self._iter_message_events(session):
            if e.body and e.body.get("agui_id") == agui_id:
                msg = payload_to_message(e.body)
                if msg:
                    self._remember_maps(msg, chat_id)
                return msg
        return None

    async def get_tool_call_by_agui_id(
        self, message_uuid: UUID, agui_id: str
    ) -> MessageToolCall | None:
        chat_id = self._msg_chat.get(message_uuid)
        if chat_id is None:
            discovered = await self._discover_chat_for_message(message_uuid)
            if discovered is None:
                return None
            chat_id = discovered

        session = await self._session_for_chat(chat_id)
        ev = await self._find_event_for_message_uuid(session, message_uuid)
        if not ev or not ev.body:
            return None
        msg = payload_to_message(ev.body)
        if not msg:
            return None
        for tc in msg.tool_calls:
            if tc.agui_id == agui_id:
                self._remember_maps(msg, chat_id)
                return tc
        return None

    async def get_chat_messages(self, chat_id: UUID) -> Sequence[Message]:
        session = await self._session_for_chat(chat_id)
        events = await self._iter_message_events(session)
        ordered = sorted(events, key=lambda e: e.sequence_id or 0)
        out: list[Message] = []
        for e in ordered:
            if e.body:
                msg = payload_to_message(e.body)
                if msg:
                    self._remember_maps(msg, chat_id)
                    out.append(msg)
        return out

    async def get_last_messages(self, chat_ids: list[UUID]) -> dict[UUID, Message]:
        result: dict[UUID, Message] = {}
        for cid in chat_ids:
            sid = await self._registry.resolve_session_id(cid)
            if not sid:
                continue

            evs = await asyncio.to_thread(
                _fetch_last_message_events, self._memory_space_id, sid
            )
            if evs and evs[-1].body:
                msg = payload_to_message(evs[-1].body)
                if msg:
                    self._remember_maps(msg, cid)
                    result[cid] = msg
        return result
