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

from pathlib import Path
from unittest.mock import patch

import pytest

from app.chats import ChatRepository
from app.config import Config
from app.deps import (
    create_deps,
    resolve_application_memory_space_id,
    sqlite_uri_to_path,
)
from app.memory import (
    MemoryChatRepository,
    MemoryIdentityRepository,
    MemoryMessageRepository,
    MemoryUserRepository,
)
from app.messages import MessageRepository
from app.users.identity import IdentityRepository
from app.users.user import UserRepository


@pytest.mark.asyncio
async def test_create_deps_uses_memory_repositories_when_enabled() -> None:
    config = Config(
        session_secret_key="test-session-secret-key",
        session_https_only=False,
        database_uri="sqlite+aiosqlite:///:memory:",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-datarobot-api-key",
        USE_APPLICATION_MEMORY_SPACE=True,
        APPLICATION_MEMORY_SPACE_ID="space-test",
    )

    with patch("app.deps.datarobot.Client"):
        async with create_deps(config) as deps:
            assert isinstance(deps.chat_repo, MemoryChatRepository)
            assert isinstance(deps.message_repo, MemoryMessageRepository)
            assert isinstance(deps.identity_repo, MemoryIdentityRepository)
            assert isinstance(deps.user_repo, MemoryUserRepository)


def test_resolve_application_memory_space_id_returns_none_when_disabled() -> None:
    config = Config(
        session_secret_key="test-secret",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-token",
    )
    assert resolve_application_memory_space_id(config) is None


def test_resolve_application_memory_space_id_returns_id_when_configured() -> None:
    config = Config(
        session_secret_key="test-secret",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-token",
        USE_APPLICATION_MEMORY_SPACE=True,
        APPLICATION_MEMORY_SPACE_ID="space-test",
    )
    assert resolve_application_memory_space_id(config) == "space-test"


def test_resolve_application_memory_space_id_returns_none_locally_without_id() -> None:
    config = Config(
        session_secret_key="test-secret",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-token",
        USE_APPLICATION_MEMORY_SPACE=True,
        APPLICATION_MEMORY_SPACE_ID=None,
    )
    assert resolve_application_memory_space_id(config) is None


def test_resolve_application_memory_space_id_raises_when_deployed_without_id() -> None:
    config = Config(
        session_secret_key="test-secret",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-token",
        USE_APPLICATION_MEMORY_SPACE=True,
        APPLICATION_MEMORY_SPACE_ID=None,
        application_id="6978ed7637491dea39936243",
    )
    with pytest.raises(RuntimeError, match="APPLICATION_MEMORY_SPACE_ID is required"):
        resolve_application_memory_space_id(config)


@pytest.mark.asyncio
async def test_create_deps_falls_back_to_sqlite_before_memory_space_is_wired() -> None:
    config = Config(
        session_secret_key="test-session-secret-key",
        session_https_only=False,
        database_uri="sqlite+aiosqlite:///:memory:",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-datarobot-api-key",
        USE_APPLICATION_MEMORY_SPACE=True,
        APPLICATION_MEMORY_SPACE_ID=None,
    )

    async with create_deps(config) as deps:
        assert isinstance(deps.chat_repo, ChatRepository)
        assert isinstance(deps.message_repo, MessageRepository)
        assert isinstance(deps.identity_repo, IdentityRepository)
        assert isinstance(deps.user_repo, UserRepository)


def test_sqlite_uri_to_path() -> None:
    assert sqlite_uri_to_path("sqlite:///path/to/db.sqlite") == Path(
        "path/to/db.sqlite"
    )
    assert sqlite_uri_to_path("sqlite:////tmp/db.sqlite") == Path("/tmp/db.sqlite")
    assert sqlite_uri_to_path("sqlite:///:memory:") is None
    assert sqlite_uri_to_path("postgresql://user:pass@localhost/dbname") is None
