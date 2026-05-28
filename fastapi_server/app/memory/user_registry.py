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
from collections.abc import Callable
from typing import Any
from uuid import UUID

from datarobot.models.memory import Session

from app.memory.constants import (
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    USER_METADATA_VERSION,
    user_by_email_description,
)
from app.memory.metadata_keys import session_metadata

logger = logging.getLogger(__name__)


class UserSessionRegistry:
    """
    Maps user lookup keys to memory-service session IDs.

    Sessions are created with indexed descriptions ``/user/email/{email}``.
    A local cache covers hot paths; on a miss the session is resolved via
    ``Session.list(..., description=...)`` for email lookups, or a metadata scan
    for id/uuid lookups.
    """

    def __init__(self, memory_space_id: str) -> None:
        self._memory_space_id = memory_space_id
        self._by_email: dict[str, str] = {}
        self._by_uuid: dict[UUID, str] = {}
        self._by_id: dict[int, str] = {}

    def register(
        self,
        *,
        session_id: str,
        email: str,
        user_uuid: UUID,
        user_id: int,
    ) -> None:
        self._by_email[email] = session_id
        self._by_uuid[user_uuid] = session_id
        self._by_id[user_id] = session_id

    def unregister(
        self,
        *,
        email: str,
        user_uuid: UUID,
        user_id: int,
    ) -> None:
        self._by_email.pop(email, None)
        self._by_uuid.pop(user_uuid, None)
        self._by_id.pop(user_id, None)

    def _register_from_metadata(self, session: Session) -> None:
        sid = session.id
        md = session_metadata(session)
        if sid is None or md.get("v") != USER_METADATA_VERSION:
            return
        try:
            user_uuid = UUID(md["user_uuid"])
            user_id = int(md["user_id"])
            email = str(md["email"])
        except (KeyError, TypeError, ValueError):
            return
        self.register(
            session_id=sid,
            email=email,
            user_uuid=user_uuid,
            user_id=user_id,
        )

    async def resolve_by_email(self, email: str) -> str | None:
        if sid := self._by_email.get(email):
            return sid

        description = user_by_email_description(email)

        def _list_by_description() -> list[Session]:
            return Session.list(
                self._memory_space_id,
                description=description,
                limit=1,
            )

        batch = await asyncio.to_thread(_list_by_description)
        if batch:
            s = batch[0]
            if s.id is not None:
                self._register_from_metadata(s)
                return s.id

        return await self._scan_metadata(
            match=lambda md: md.get("email") == email,
        )

    async def resolve_by_uuid(self, user_uuid: UUID) -> str | None:
        if sid := self._by_uuid.get(user_uuid):
            return sid

        return await self._scan_metadata(
            match=lambda md: md.get("user_uuid") == str(user_uuid),
        )

    async def resolve_by_id(self, user_id: int) -> str | None:
        if sid := self._by_id.get(user_id):
            return sid

        return await self._scan_metadata(
            match=lambda md: md.get("user_id") == user_id,
        )

    async def _scan_metadata(
        self, *, match: Callable[[dict[str, Any]], bool]
    ) -> str | None:
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
                return None
            for s in batch:
                md = session_metadata(s)
                if md.get("v") != USER_METADATA_VERSION:
                    continue
                if match(md):
                    if s.id is not None:
                        self._register_from_metadata(s)
                        return s.id
            offset += len(batch)
