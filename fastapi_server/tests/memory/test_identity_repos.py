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

from app.memory.constants import identity_by_user_provider_description
from app.memory.identity_registry import IdentitySessionRegistry
from app.memory.identity_repos import MemoryIdentityRepository
from app.users.identity import AuthSchema, IdentityUpdate
from tests.memory.helpers import memory_identity_session


@pytest.mark.asyncio
async def test_upsert_identity_creates_session_with_user_provider_description() -> None:
    created = memory_identity_session(
        "sess-new",
        identity_uuid=uuidpkg.uuid4(),
        identity_id=1001,
        provider_type="google",
        provider_user_id="google-user-1",
        user_id=5,
    )

    registry = IdentitySessionRegistry("space-1")
    repo = MemoryIdentityRepository("space-1", registry)

    with (
        patch(
            "app.memory.identity_repos.Session.list",
            return_value=[],
        ),
        patch(
            "app.memory.identity_repos.Session.create",
            return_value=created,
        ) as create_mock,
    ):
        identity = await repo.upsert_identity(
            user_id=5,
            auth_type=AuthSchema.OAUTH2,
            provider_id="google",
            provider_type="google",
            provider_user_id="google-user-1",
        )

    create_mock.assert_called_once()
    assert create_mock.call_args[0][0] == "space-1"
    assert len(create_mock.call_args[0][1]) == 1
    assert create_mock.call_args[1][
        "description"
    ] == identity_by_user_provider_description(5, "google")
    assert identity.user_id == 5
    assert identity.provider_user_id == "google-user-1"
    assert identity.id == 1001


@pytest.mark.asyncio
async def test_upsert_identity_updates_existing_metadata() -> None:
    identity_uuid = uuidpkg.uuid4()
    existing = memory_identity_session(
        "sess-1",
        identity_uuid=identity_uuid,
        identity_id=2002,
        provider_type="google",
        provider_user_id="google-user-2",
        user_id=3,
    )
    updated = memory_identity_session(
        "sess-1",
        identity_uuid=identity_uuid,
        identity_id=2002,
        provider_type="google",
        provider_user_id="google-user-2",
        user_id=3,
    )
    updated.metadata["access_token"] = "new-token"

    registry = IdentitySessionRegistry("space-1")
    registry.register(
        session_id="sess-1",
        user_id=3,
        provider_type="google",
        provider_user_id="google-user-2",
        identity_uuid=identity_uuid,
        identity_id=2002,
    )
    repo = MemoryIdentityRepository("space-1", registry)

    existing.update = MagicMock()
    with patch(
        "app.memory.identity_repos.Session.get",
        side_effect=[existing, existing, updated],
    ):
        identity = await repo.upsert_identity(
            user_id=3,
            auth_type=AuthSchema.OAUTH2,
            provider_id="google",
            provider_type="google",
            provider_user_id="google-user-2",
            update=IdentityUpdate(access_token="new-token"),
        )

    existing.update.assert_called_once()
    assert identity.id == 2002
    assert identity.access_token == "new-token"


@pytest.mark.asyncio
async def test_get_by_external_user_id_filters_auth_type() -> None:
    identity_uuid = uuidpkg.uuid4()
    session = memory_identity_session(
        "sess-1",
        identity_uuid=identity_uuid,
        identity_id=3003,
        provider_type="google",
        provider_user_id="ext-1",
        user_id=1,
        auth_type=AuthSchema.DATAROBOT,
    )

    registry = IdentitySessionRegistry("space-1")
    registry.register(
        session_id="sess-1",
        user_id=1,
        provider_type="google",
        provider_user_id="ext-1",
        identity_uuid=identity_uuid,
        identity_id=3003,
    )
    repo = MemoryIdentityRepository("space-1", registry)

    with patch("app.memory.identity_repos.Session.get", return_value=session):
        assert (
            await repo.get_by_external_user_id(
                "google", "ext-1", auth_type=AuthSchema.OAUTH2
            )
            is None
        )
        found = await repo.get_by_external_user_id(
            "google", "ext-1", auth_type=AuthSchema.DATAROBOT
        )
    assert found is not None
    assert found.id == 3003


@pytest.mark.asyncio
async def test_update_identity_reregisters_provider_cache_on_provider_user_id_change() -> (
    None
):
    identity_uuid = uuidpkg.uuid4()
    session = memory_identity_session(
        "sess-upd",
        identity_uuid=identity_uuid,
        identity_id=5005,
        provider_type="google",
        provider_user_id="old-user",
        user_id=2,
    )
    updated_session = memory_identity_session(
        "sess-upd",
        identity_uuid=identity_uuid,
        identity_id=5005,
        provider_type="google",
        provider_user_id="new-user",
        user_id=2,
    )
    session.update = MagicMock()

    registry = IdentitySessionRegistry("space-1")
    registry.register(
        session_id="sess-upd",
        user_id=2,
        provider_type="google",
        provider_user_id="old-user",
        identity_uuid=identity_uuid,
        identity_id=5005,
    )
    repo = MemoryIdentityRepository("space-1", registry)

    with patch(
        "app.memory.identity_repos.Session.get",
        side_effect=[session, updated_session],
    ):
        result = await repo.update_identity(
            5005, IdentityUpdate(provider_user_id="new-user")
        )

    assert result is not None
    assert result.provider_user_id == "new-user"

    with patch("app.memory.identity_registry.Session.list") as list_mock:
        assert await registry.resolve_by_provider("google", "new-user") == "sess-upd"
    list_mock.assert_not_called()

    with patch("app.memory.identity_registry.Session.list", return_value=[]):
        assert await registry.resolve_by_provider("google", "old-user") is None


@pytest.mark.asyncio
async def test_delete_by_id_removes_session_and_unregisters() -> None:
    identity_uuid = uuidpkg.uuid4()
    session = memory_identity_session(
        "sess-del",
        identity_uuid=identity_uuid,
        identity_id=4004,
        provider_type="box",
        provider_user_id="box-1",
        user_id=9,
    )
    session.delete = MagicMock()

    registry = IdentitySessionRegistry("space-1")
    registry.register(
        session_id="sess-del",
        user_id=9,
        provider_type="box",
        provider_user_id="box-1",
        identity_uuid=identity_uuid,
        identity_id=4004,
    )
    repo = MemoryIdentityRepository("space-1", registry)

    with patch("app.memory.identity_repos.Session.get", return_value=session):
        await repo.delete_by_id(4004)

    session.delete.assert_called_once()
    with patch("app.memory.identity_registry.Session.list", return_value=[]):
        assert await registry.resolve_by_id(4004) is None
