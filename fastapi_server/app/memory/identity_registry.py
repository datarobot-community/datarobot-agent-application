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
    IDENTITY_METADATA_VERSION,
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    identity_by_user_provider_description,
)
from app.memory.metadata_keys import session_metadata

logger = logging.getLogger(__name__)


class IdentitySessionRegistry:
    """
    Maps identity lookup keys to memory-service session IDs.

    Sessions are created with indexed descriptions
    ``/user/{user_id}/identity/{provider_type}``. A local cache covers hot paths;
    on a miss the session is resolved via ``Session.list(..., description=...)`` for
    user/provider lookups, or a metadata scan for provider/external-user lookups.
    """

    def __init__(self, memory_space_id: str) -> None:
        self._memory_space_id = memory_space_id
        self._by_user_provider: dict[tuple[int, str], str] = {}
        self._by_provider: dict[tuple[str, str], str] = {}
        self._by_uuid: dict[UUID, str] = {}
        self._by_id: dict[int, str] = {}

    def register(
        self,
        *,
        session_id: str,
        user_id: int,
        provider_type: str,
        provider_user_id: str,
        identity_uuid: UUID,
        identity_id: int,
    ) -> None:
        self._by_user_provider[(user_id, provider_type)] = session_id
        self._by_provider[(provider_type, provider_user_id)] = session_id
        self._by_uuid[identity_uuid] = session_id
        self._by_id[identity_id] = session_id

    def unregister(
        self,
        *,
        user_id: int,
        provider_type: str,
        provider_user_id: str,
        identity_uuid: UUID,
        identity_id: int,
    ) -> None:
        self._by_user_provider.pop((user_id, provider_type), None)
        self._by_provider.pop((provider_type, provider_user_id), None)
        self._by_uuid.pop(identity_uuid, None)
        self._by_id.pop(identity_id, None)

    def _register_from_metadata(self, session: Session) -> None:
        sid = session.id
        md = session_metadata(session)
        if sid is None or md.get("v") != IDENTITY_METADATA_VERSION:
            return
        try:
            identity_uuid = UUID(md["identity_uuid"])
            identity_id = int(md["identity_id"])
            user_id = int(md["user_id"])
            provider_type = str(md["provider_type"])
            provider_user_id = str(md["provider_user_id"])
        except (KeyError, TypeError, ValueError):
            return
        self.register(
            session_id=sid,
            user_id=user_id,
            provider_type=provider_type,
            provider_user_id=provider_user_id,
            identity_uuid=identity_uuid,
            identity_id=identity_id,
        )

    async def resolve_by_provider(
        self, provider_type: str, provider_user_id: str
    ) -> str | None:
        key = (provider_type, provider_user_id)
        if sid := self._by_provider.get(key):
            return sid

        return await self._scan_metadata(
            match=lambda md: (
                md.get("provider_type") == provider_type
                and md.get("provider_user_id") == provider_user_id
            ),
        )

    async def resolve_by_user_provider(
        self, user_id: int, provider_type: str
    ) -> str | None:
        key = (user_id, provider_type)
        if sid := self._by_user_provider.get(key):
            return sid

        description = identity_by_user_provider_description(user_id, provider_type)

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
            match=lambda md: (
                md.get("user_id") == user_id
                and md.get("provider_type") == provider_type
            ),
        )

    async def resolve_by_uuid(self, identity_uuid: UUID) -> str | None:
        if sid := self._by_uuid.get(identity_uuid):
            return sid

        return await self._scan_metadata(
            match=lambda md: md.get("identity_uuid") == str(identity_uuid),
        )

    async def resolve_by_id(self, identity_id: int) -> str | None:
        if sid := self._by_id.get(identity_id):
            return sid

        return await self._scan_metadata(
            match=lambda md: md.get("identity_id") == identity_id,
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
                if md.get("v") != IDENTITY_METADATA_VERSION:
                    continue
                if match(md):
                    if s.id is not None:
                        self._register_from_metadata(s)
                        return s.id
            offset += len(batch)
