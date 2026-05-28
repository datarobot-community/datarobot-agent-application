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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.memory.constants import user_by_email_description
from app.memory.user_registry import UserSessionRegistry
from app.memory.user_repos import MemoryUserRepository
from app.users.user import LanguageEnum, ThemeEnum, UserCreate
from tests.memory.helpers import memory_user_session


def _identity_repo_mock() -> MagicMock:
    repo = MagicMock()
    repo.list_by_user_id = AsyncMock(return_value=[])
    return repo


@pytest.mark.asyncio
async def test_create_user_uses_email_description() -> None:
    user_uuid = uuidpkg.uuid4()
    created = memory_user_session(
        "sess-new",
        user_uuid=user_uuid,
        user_id=1001,
        email="new@example.com",
    )

    registry = UserSessionRegistry("space-1")
    repo = MemoryUserRepository("space-1", registry, _identity_repo_mock())

    with (
        patch("app.memory.user_repos.Session.list", return_value=[]),
        patch("app.memory.user_repos.Session.get", return_value=created),
        patch(
            "app.memory.user_repos.Session.create",
            return_value=created,
        ) as create_mock,
    ):
        user = await repo.create_user(
            UserCreate(email="new@example.com", first_name="Al", last_name="Bo")
        )

    create_mock.assert_called_once()
    assert create_mock.call_args[1]["description"] == user_by_email_description(
        "new@example.com"
    )
    assert user.email == "new@example.com"
    assert user.id == 1001


@pytest.mark.asyncio
async def test_create_user_raises_integrity_error_on_duplicate_email() -> None:
    user_uuid = uuidpkg.uuid4()
    registry = UserSessionRegistry("space-1")
    registry.register(
        session_id="sess-1",
        email="dup@example.com",
        user_uuid=user_uuid,
        user_id=42,
    )
    repo = MemoryUserRepository("space-1", registry, _identity_repo_mock())

    with patch("app.memory.user_repos.Session.get") as get_mock:
        get_mock.return_value = memory_user_session(
            "sess-1",
            user_uuid=user_uuid,
            user_id=42,
            email="dup@example.com",
        )
        with pytest.raises(IntegrityError):
            await repo.create_user(UserCreate(email="dup@example.com"))


@pytest.mark.asyncio
async def test_update_user_settings_patches_metadata() -> None:
    user_uuid = uuidpkg.uuid4()
    existing = memory_user_session(
        "sess-1",
        user_uuid=user_uuid,
        user_id=7,
        email="settings@example.com",
    )
    registry = UserSessionRegistry("space-1")
    registry.register(
        session_id="sess-1",
        email="settings@example.com",
        user_uuid=user_uuid,
        user_id=7,
    )
    repo = MemoryUserRepository("space-1", registry, _identity_repo_mock())

    def fake_update(**kwargs: object) -> None:
        existing.metadata = kwargs["metadata"]

    with (
        patch("app.memory.user_repos.Session.get", return_value=existing),
        patch.object(existing, "update", side_effect=fake_update),
    ):
        user = await repo.update_user_settings(
            user_id=7, theme=ThemeEnum.dark, language=LanguageEnum.fr
        )

    assert user.theme == ThemeEnum.dark
    assert user.language == LanguageEnum.fr
