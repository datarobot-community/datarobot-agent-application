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

from app.memory.constants import user_by_email_description
from app.memory.user_registry import UserSessionRegistry
from tests.memory.helpers import memory_user_session


@pytest.mark.asyncio
async def test_user_registry_resolve_by_email_lists_and_caches() -> None:
    user_uuid = uuidpkg.uuid4()
    target = memory_user_session(
        "sess-1",
        user_uuid=user_uuid,
        user_id=7,
        email="alice@example.com",
    )

    def fake_list(
        space_id: str,
        *,
        description: str | None = None,
        limit: int | None = None,
    ) -> list[object]:
        assert space_id == "space-1"
        assert description == user_by_email_description("alice@example.com")
        assert limit == 1
        return [target]

    registry = UserSessionRegistry("space-1")
    with patch("app.memory.user_registry.Session.list", side_effect=fake_list):
        sid = await registry.resolve_by_email("alice@example.com")

    assert sid == "sess-1"
    with patch("app.memory.user_registry.Session.list") as list_mock:
        assert await registry.resolve_by_email("alice@example.com") == "sess-1"
    list_mock.assert_not_called()


@pytest.mark.asyncio
async def test_user_registry_resolve_by_uuid_uses_cache() -> None:
    user_uuid = uuidpkg.uuid4()
    registry = UserSessionRegistry("space-1")
    registry.register(
        session_id="sess-2",
        email="bob@example.com",
        user_uuid=user_uuid,
        user_id=99,
    )

    with patch("app.memory.user_registry.Session.list") as list_mock:
        sid = await registry.resolve_by_uuid(user_uuid)

    assert sid == "sess-2"
    list_mock.assert_not_called()
