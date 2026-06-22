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

"""Helpers for idempotent memory-space session create and patch operations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from datarobot.errors import ClientError, MemorySessionDeduplicationError
from datarobot.models.memory import Session

MEMORY_SESSION_PATCH_RETRIES = 3


async def create_memory_session(
    memory_space_id: str,
    participants: list[str],
    *,
    deduplication_key: str,
    metadata: dict[str, Any] | None = None,
    description: str | None = None,
) -> tuple[Session, bool]:
    """Create a session, adopting the existing one when the deduplication key collides."""

    def _create() -> tuple[Session, bool]:
        try:
            return (
                Session.create(
                    memory_space_id,
                    participants,
                    metadata=metadata,
                    description=description,
                    deduplication_key=deduplication_key,
                ),
                False,
            )
        except MemorySessionDeduplicationError as exc:
            if exc.existing_session_id is None:
                raise
            return Session.get(memory_space_id, exc.existing_session_id), True

    return await asyncio.to_thread(_create)


async def patch_memory_session(
    memory_space_id: str,
    session_id: str,
    *,
    build_patch: Callable[[Session], dict[str, object]],
    max_retries: int = MEMORY_SESSION_PATCH_RETRIES,
) -> Session:
    """Apply a read-modify-write patch, retrying on version conflicts (HTTP 409)."""

    def _patch() -> Session:
        last_error: ClientError | None = None
        for _ in range(max_retries):
            session = Session.get(memory_space_id, session_id)
            patch_fields = build_patch(session)
            if not patch_fields:
                return session
            try:
                session.update(**patch_fields)
                return Session.get(memory_space_id, session_id)
            except ClientError as exc:
                if exc.status_code != 409:
                    raise
                last_error = exc
        assert last_error is not None
        raise last_error

    return await asyncio.to_thread(_patch)
