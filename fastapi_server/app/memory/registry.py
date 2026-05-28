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
import logging
from uuid import UUID

from datarobot.models.memory import Session

from app.memory.constants import (
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    chat_session_description,
)

logger = logging.getLogger(__name__)


class ChatSessionRegistry:
    """
    Maps internal chat UUIDs to memory-service session IDs.

    New sessions use indexed descriptions (`/thread/{id}` or `/chat/{uuid}`). A local
    cache covers hot paths; on a miss (for example after a process restart), the
    session is resolved via ``Session.list(..., description=...)``, with a metadata
    scan fallback for legacy or thread-keyed sessions.
    """

    def __init__(self, memory_space_id: str) -> None:
        self._memory_space_id = memory_space_id
        self._chat_to_session: dict[UUID, str] = {}

    def register(self, chat_uuid: UUID, session_id: str) -> None:
        self._chat_to_session[chat_uuid] = session_id

    def unregister(self, chat_uuid: UUID) -> None:
        self._chat_to_session.pop(chat_uuid, None)

    def get_session_id(self, chat_uuid: UUID) -> str | None:
        return self._chat_to_session.get(chat_uuid)

    async def resolve_session_id(self, chat_uuid: UUID) -> str | None:
        if sid := self.get_session_id(chat_uuid):
            return sid

        description = chat_session_description(chat_uuid)

        def _list_by_description() -> list[Session]:
            return Session.list(
                self._memory_space_id,
                description=description,
                limit=1,
            )

        batch = await asyncio.to_thread(_list_by_description)
        if batch:
            sid = batch[0].id
            if sid is not None:
                self.register(chat_uuid, sid)
                return sid

        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_page(o: int, lim: int) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return Session.list(
                    self._memory_space_id,
                    offset=o,
                    limit=capped,
                )

            batch = await asyncio.to_thread(_list_page, offset, page_size)
            if not batch:
                logger.debug(
                    "No memory session found for chat_uuid=%s (description=%s)",
                    chat_uuid,
                    description,
                )
                return None
            for s in batch:
                sid = s.id
                if sid is None:
                    continue
                md = s.metadata or {}
                if md.get("chat_uuid") == str(chat_uuid):
                    self.register(chat_uuid, sid)
                    return sid
            offset += len(batch)
