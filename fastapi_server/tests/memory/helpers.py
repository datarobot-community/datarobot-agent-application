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
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.memory.constants import IDENTITY_METADATA_VERSION, USER_METADATA_VERSION
from app.memory.identity_repos import identity_to_metadata
from app.memory.user_repos import user_to_metadata
from app.users.identity import AuthSchema, Identity
from app.users.user import User


def memory_identity_session(
    session_id: str,
    *,
    identity_uuid: uuidpkg.UUID,
    identity_id: int,
    provider_type: str,
    provider_user_id: str,
    user_id: int,
    auth_type: AuthSchema = AuthSchema.OAUTH2,
) -> MagicMock:
    identity = Identity(
        id=identity_id,
        uuid=identity_uuid,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        type=auth_type,
        user_id=user_id,
        provider_id="prov",
        provider_type=provider_type,
        provider_user_id=provider_user_id,
    )
    s = MagicMock()
    s.id = session_id
    s.created_at = identity.created_at
    s.metadata = identity_to_metadata(identity)
    assert s.metadata["v"] == IDENTITY_METADATA_VERSION
    return s


def memory_session(
    session_id: str,
    *,
    thread_id: str,
    user_uuid: uuidpkg.UUID,
    chat_uuid: uuidpkg.UUID | None = None,
    name: str = "Chat",
    participants: list[str] | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id
    s.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s.metadata = {
        "thread_id": thread_id,
        "user_uuid": str(user_uuid),
        "chat_uuid": str(chat_uuid or uuidpkg.uuid4()),
        "name": name,
    }
    s.participants = participants or []
    return s


def memory_user_session(
    session_id: str,
    *,
    user_uuid: uuidpkg.UUID,
    user_id: int,
    email: str = "u@example.com",
) -> MagicMock:
    user = User(
        id=user_id,
        uuid=user_uuid,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        email=email,
        first_name="Te",
        last_name="St",
    )
    s = MagicMock()
    s.id = session_id
    s.created_at = user.created_at
    s.metadata = user_to_metadata(user)
    assert s.metadata["v"] == USER_METADATA_VERSION
    return s


def memory_user(uid: uuidpkg.UUID) -> User:
    return User(
        id=1,
        uuid=uid,
        email="u@example.com",
        first_name="Te",
        last_name="St",
    )
