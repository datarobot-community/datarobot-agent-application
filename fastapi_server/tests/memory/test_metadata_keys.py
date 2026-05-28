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
from unittest.mock import MagicMock

from app.memory.metadata_keys import (
    camel_to_snake,
    normalize_metadata,
    session_metadata,
)
from app.memory.user_repos import metadata_to_user


def test_camel_to_snake() -> None:
    assert camel_to_snake("userUuid") == "user_uuid"
    assert camel_to_snake("identityId") == "identity_id"
    assert camel_to_snake("user_uuid") == "user_uuid"


def test_normalize_metadata_prefers_snake_case() -> None:
    md = normalize_metadata(
        {
            "userUuid": "wrong",
            "user_uuid": "right",
            "v": 2,
        }
    )
    assert md["user_uuid"] == "right"


def test_metadata_to_user_reads_camel_case_from_api() -> None:
    user_uuid = uuidpkg.uuid4()
    session = MagicMock()
    session.metadata = {
        "v": 2,
        "userUuid": str(user_uuid),
        "userId": 42,
        "email": "dev@example.com",
        "theme": "system",
        "language": "en",
        "createdAt": "2026-01-01T00:00:00+00:00",
    }
    session.created_at = None

    user = metadata_to_user(session)
    assert user is not None
    assert user.uuid == user_uuid
    assert user.id == 42
    assert user.email == "dev@example.com"


def test_session_metadata_helper() -> None:
    session = MagicMock()
    session.metadata = {"threadId": "t-1", "chatUuid": "c-1"}
    assert session_metadata(session) == {"thread_id": "t-1", "chat_uuid": "c-1"}
