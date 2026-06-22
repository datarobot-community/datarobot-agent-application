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
from unittest.mock import MagicMock, patch

import pytest
from datarobot.errors import ClientError, MemorySessionDeduplicationError

from app.memory.constants import (
    DEDUPLICATION_KEY_LENGTH,
    chat_deduplication_key,
    identity_deduplication_key,
    user_email_deduplication_key,
)
from app.memory.sessions import create_memory_session, patch_memory_session


def test_deduplication_keys_are_stable_and_within_limit() -> None:
    user_uuid = uuidpkg.uuid4()
    chat_key = chat_deduplication_key(user_uuid, "thread-1")
    email_key = user_email_deduplication_key("user@example.com")
    identity_key = identity_deduplication_key(42, "google")

    assert len(chat_key) == DEDUPLICATION_KEY_LENGTH
    assert chat_key == chat_deduplication_key(user_uuid, "thread-1")
    assert email_key == user_email_deduplication_key("user@example.com")
    assert identity_key == identity_deduplication_key(42, "google")
    assert chat_key != email_key != identity_key


@pytest.mark.asyncio
async def test_create_memory_session_returns_created_session() -> None:
    created = MagicMock()
    created.id = "sess-new"

    with patch(
        "app.memory.sessions.Session.create",
        return_value=created,
    ) as create_mock:
        session, duplicated = await create_memory_session(
            "space-1",
            ["participant"],
            deduplication_key="dedupe-key",
            metadata={"k": "v"},
            description="/thread/t1",
        )

    assert duplicated is False
    assert session is created
    create_mock.assert_called_once_with(
        "space-1",
        ["participant"],
        metadata={"k": "v"},
        description="/thread/t1",
        deduplication_key="dedupe-key",
    )


@pytest.mark.asyncio
async def test_create_memory_session_adopts_existing_session_on_conflict() -> None:
    created = MagicMock()
    created.id = "sess-existing"
    error = MemorySessionDeduplicationError(
        "conflict",
        409,
        json={"existingSessionId": "sess-existing"},
    )

    with (
        patch(
            "app.memory.sessions.Session.create",
            side_effect=error,
        ),
        patch(
            "app.memory.sessions.Session.get",
            return_value=created,
        ) as get_mock,
    ):
        session, duplicated = await create_memory_session(
            "space-1",
            ["participant"],
            deduplication_key="dedupe-key",
        )

    assert duplicated is True
    assert session is created
    get_mock.assert_called_once_with("space-1", "sess-existing")


@pytest.mark.asyncio
async def test_patch_memory_session_applies_update() -> None:
    loaded = MagicMock()
    loaded.id = "sess-1"
    loaded.version = 3
    refreshed = MagicMock()
    refreshed.id = "sess-1"

    with patch(
        "app.memory.sessions.Session.get",
        side_effect=[loaded, refreshed],
    ) as get_mock:
        result = await patch_memory_session(
            "space-1",
            "sess-1",
            build_patch=lambda _s: {"metadata": {"token": "new"}},
        )

    assert result is refreshed
    loaded.update.assert_called_once_with(metadata={"token": "new"})
    assert get_mock.call_count == 2


@pytest.mark.asyncio
async def test_patch_memory_session_retries_on_version_conflict() -> None:
    stale = MagicMock()
    stale.id = "sess-1"
    stale.version = 1
    stale.update.side_effect = ClientError("conflict", 409)

    current = MagicMock()
    current.id = "sess-1"
    current.version = 2

    refreshed = MagicMock()
    refreshed.id = "sess-1"

    with patch(
        "app.memory.sessions.Session.get",
        side_effect=[stale, current, refreshed],
    ) as get_mock:
        result = await patch_memory_session(
            "space-1",
            "sess-1",
            build_patch=lambda _s: {"metadata": {"token": "new"}},
        )

    assert result is refreshed
    stale.update.assert_called_once()
    current.update.assert_called_once_with(metadata={"token": "new"})
    assert get_mock.call_count == 3
