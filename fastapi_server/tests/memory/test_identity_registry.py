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

from app.memory.constants import identity_by_user_provider_description
from app.memory.identity_registry import IdentitySessionRegistry
from tests.memory.helpers import memory_identity_session


@pytest.mark.asyncio
async def test_identity_registry_resolve_by_provider_scans_metadata_and_caches() -> (
    None
):
    identity_uuid = uuidpkg.uuid4()
    target = memory_identity_session(
        "sess-1",
        identity_uuid=identity_uuid,
        identity_id=42,
        provider_type="google",
        provider_user_id="uid-1",
        user_id=7,
    )
    other = memory_identity_session(
        "sess-2",
        identity_uuid=uuidpkg.uuid4(),
        identity_id=43,
        provider_type="google",
        provider_user_id="uid-2",
        user_id=8,
    )

    def fake_list(
        space_id: str,
        *,
        offset: int = 0,
        limit: int | None = None,
        description: str | None = None,
    ) -> list[object]:
        assert space_id == "space-1"
        assert description is None
        assert offset == 0
        assert limit == 100
        return [other, target]

    registry = IdentitySessionRegistry("space-1")
    with patch("app.memory.identity_registry.Session.list", side_effect=fake_list):
        sid = await registry.resolve_by_provider("google", "uid-1")

    assert sid == "sess-1"
    with patch("app.memory.identity_registry.Session.list") as list_mock:
        assert await registry.resolve_by_provider("google", "uid-1") == "sess-1"
    list_mock.assert_not_called()


@pytest.mark.asyncio
async def test_identity_registry_resolve_by_uuid_uses_cache() -> None:
    identity_uuid = uuidpkg.uuid4()
    registry = IdentitySessionRegistry("space-1")
    registry.register(
        session_id="sess-2",
        user_id=3,
        provider_type="google",
        provider_user_id="uid-2",
        identity_uuid=identity_uuid,
        identity_id=99,
    )

    with patch("app.memory.identity_registry.Session.list") as list_mock:
        sid = await registry.resolve_by_uuid(identity_uuid)

    assert sid == "sess-2"
    list_mock.assert_not_called()


@pytest.mark.asyncio
async def test_identity_registry_resolve_by_user_provider_lists_and_caches() -> None:
    identity_uuid = uuidpkg.uuid4()
    target = memory_identity_session(
        "sess-user",
        identity_uuid=identity_uuid,
        identity_id=42,
        provider_type="google",
        provider_user_id="uid-1",
        user_id=7,
    )

    def fake_list(
        space_id: str,
        *,
        description: str | None = None,
        limit: int | None = None,
    ) -> list[object]:
        assert space_id == "space-1"
        assert description == identity_by_user_provider_description(7, "google")
        assert limit == 1
        return [target]

    registry = IdentitySessionRegistry("space-1")
    with patch("app.memory.identity_registry.Session.list", side_effect=fake_list):
        sid = await registry.resolve_by_user_provider(7, "google")

    assert sid == "sess-user"
    with patch("app.memory.identity_registry.Session.list") as list_mock:
        assert await registry.resolve_by_user_provider(7, "google") == "sess-user"
    list_mock.assert_not_called()
