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
from unittest.mock import patch

import pytest

from app.memory.constants import chat_session_description
from app.memory.registry import ChatSessionRegistry
from tests.memory.helpers import memory_session


@pytest.mark.asyncio
async def test_registry_register_get_unregister() -> None:
    registry = ChatSessionRegistry("space-1")
    chat_uuid = uuidpkg.uuid4()

    registry.register(chat_uuid, "sess-a")
    assert registry.get_session_id(chat_uuid) == "sess-a"

    registry.unregister(chat_uuid)
    assert registry.get_session_id(chat_uuid) is None


@pytest.mark.asyncio
async def test_resolve_session_id_returns_cached_without_listing() -> None:
    registry = ChatSessionRegistry("space-1")
    chat_uuid = uuidpkg.uuid4()
    registry.register(chat_uuid, "sess-cached")

    with patch("app.memory.registry.Session.list") as list_mock:
        sid = await registry.resolve_session_id(chat_uuid)

    assert sid == "sess-cached"
    list_mock.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_id_lists_by_description_and_caches() -> None:
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    chat_uuid = uuidpkg.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    target = memory_session(
        "target-session",
        thread_id="t1",
        user_uuid=user_uuid,
        chat_uuid=chat_uuid,
    )

    def fake_list(
        space_id: str,
        *,
        description: str | None = None,
        limit: int | None = None,
    ) -> list[object]:
        assert space_id == "space-1"
        assert description == chat_session_description(chat_uuid)
        assert limit == 1
        return [target]

    registry = ChatSessionRegistry("space-1")
    with patch("app.memory.registry.Session.list", side_effect=fake_list):
        sid = await registry.resolve_session_id(chat_uuid)

    assert sid == "target-session"
    assert registry.get_session_id(chat_uuid) == "target-session"


@pytest.mark.asyncio
async def test_resolve_session_id_falls_back_to_metadata_scan() -> None:
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")
    chat_uuid = uuidpkg.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    target = memory_session(
        "target-session",
        thread_id="t1",
        user_uuid=user_uuid,
        chat_uuid=chat_uuid,
    )

    def fake_list(
        space_id: str,
        *,
        description: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> list[object]:
        assert space_id == "space-1"
        if description is not None:
            return []
        assert offset == 0
        return [target]

    registry = ChatSessionRegistry("space-1")
    with patch("app.memory.registry.Session.list", side_effect=fake_list):
        sid = await registry.resolve_session_id(chat_uuid)

    assert sid == "target-session"
    assert registry.get_session_id(chat_uuid) == "target-session"


@pytest.mark.asyncio
async def test_resolve_session_id_returns_none_when_not_found() -> None:
    registry = ChatSessionRegistry("space-1")

    with patch("app.memory.registry.Session.list", return_value=[]):
        sid = await registry.resolve_session_id(uuidpkg.uuid4())

    assert sid is None
