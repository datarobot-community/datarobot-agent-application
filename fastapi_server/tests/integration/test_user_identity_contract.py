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

"""
Contract tests: User ↔ Identity integration across storage backends.

These tests verify that get_user() returns a User with populated identities
and a working to_auth_ctx(), regardless of whether SQL or Memory Service
is used as the storage backend.

This guards against the "split-brain" bug where identities stored in one
backend are invisible to User objects loaded from another, silently
breaking OAuth flows, session creation, and AuthCtx propagation.
"""

from __future__ import annotations

import uuid as uuidpkg
from dataclasses import dataclass
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
from sqlmodel import SQLModel

from app.db import create_db_ctx
from app.memory.identity_registry import IdentitySessionRegistry
from app.memory.identity_repos import MemoryIdentityRepository
from app.memory.user_registry import UserSessionRegistry
from app.memory.user_repos import MemoryUserRepository
from app.repo_types import IdentityRepositoryLike, UserRepositoryLike
from app.users.identity import AuthSchema, IdentityCreate, IdentityRepository
from app.users.user import UserCreate, UserRepository
from tests.memory.helpers import memory_identity_session, memory_user_session

# ---------------------------------------------------------------------------
# Abstraction: seeded repo pair ready for the contract assertion
# ---------------------------------------------------------------------------


@dataclass
class SeededRepoPair:
    """Repos with a user and identity already created, ready for get_user()."""

    user_repo: UserRepositoryLike
    identity_repo: IdentityRepositoryLike
    user_id: int
    provider_type: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROVIDER_TYPE = "google"
PROVIDER_USER_ID = "google-contract-1"


# ---------------------------------------------------------------------------
# Backend setup helpers
# ---------------------------------------------------------------------------


async def _setup_sql() -> AsyncGenerator[SeededRepoPair, None]:
    """SQL backend: real in-memory SQLite with a user + identity pre-created."""
    db = await create_db_ctx("sqlite+aiosqlite:///:memory:")
    async with db.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    user_repo = UserRepository(db)
    identity_repo = IdentityRepository(db)

    user = await user_repo.create_user(
        UserCreate(email="contract-sql@example.com", first_name="Al", last_name="Bo")
    )
    await identity_repo.create_identity(
        IdentityCreate(
            user_id=user.id,
            provider_id=PROVIDER_TYPE,
            provider_type=PROVIDER_TYPE,
            provider_user_id=PROVIDER_USER_ID,
        )
    )

    assert user.id is not None
    yield SeededRepoPair(
        user_repo=user_repo,
        identity_repo=identity_repo,
        user_id=user.id,
        provider_type=PROVIDER_TYPE,
    )

    await db.shutdown()


async def _setup_memory() -> AsyncGenerator[SeededRepoPair, None]:
    """Memory backend: mock Session API with a user + identity pre-populated."""
    space_id = "space-contract-test"
    user_id = 42
    user_uuid = uuidpkg.uuid4()
    identity_uuid = uuidpkg.uuid4()
    email = "contract-memory@example.com"

    identity_registry = IdentitySessionRegistry(space_id)
    identity_repo = MemoryIdentityRepository(space_id, identity_registry)
    user_registry = UserSessionRegistry(space_id)
    user_repo = MemoryUserRepository(space_id, user_registry, identity_repo)

    user_registry.register(
        session_id="sess-u1",
        email=email,
        user_uuid=user_uuid,
        user_id=user_id,
    )

    user_sess = memory_user_session(
        "sess-u1",
        user_uuid=user_uuid,
        user_id=user_id,
        email=email,
    )
    identity_sess = memory_identity_session(
        "sess-i1",
        identity_uuid=identity_uuid,
        identity_id=9001,
        provider_type=PROVIDER_TYPE,
        provider_user_id=PROVIDER_USER_ID,
        user_id=user_id,
    )

    with (
        patch(
            "app.memory.user_repos.Session.get",
            return_value=user_sess,
        ),
        patch(
            "app.memory.identity_repos.Session.list",
            side_effect=[[identity_sess], []],
        ),
    ):
        yield SeededRepoPair(
            user_repo=user_repo,
            identity_repo=identity_repo,
            user_id=user_id,
            provider_type=PROVIDER_TYPE,
        )


_BACKENDS = {
    "sql": _setup_sql,
    "memory": _setup_memory,
}


# ---------------------------------------------------------------------------
# Parametrized fixture — only the selected backend is instantiated
# ---------------------------------------------------------------------------


@pytest.fixture(params=list(_BACKENDS.keys()))
async def seeded_repos(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[SeededRepoPair, None]:
    """Yields a seeded (user + identity) repo pair for each storage backend."""
    setup_fn = _BACKENDS[request.param]
    async for pair in setup_fn():
        yield pair


# ---------------------------------------------------------------------------
# Contract tests — backend-agnostic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_returns_populated_identities(
    seeded_repos: SeededRepoPair,
) -> None:
    """get_user() must return a User with populated identities.

    If this fails on the 'memory' variant but passes on 'sql',
    the split-brain bug has been reintroduced.
    """
    loaded = await seeded_repos.user_repo.get_user(user_id=seeded_repos.user_id)

    assert loaded is not None, "get_user() returned None"
    assert len(loaded.identities) == 1, (
        f"expected 1 identity, got {len(loaded.identities)} — "
        f"OAuth flows will silently break"
    )
    assert loaded.identities[0].provider_type == seeded_repos.provider_type
    assert loaded.identities[0].type == AuthSchema.OAUTH2


@pytest.mark.asyncio
async def test_to_auth_ctx_propagates_identities(
    seeded_repos: SeededRepoPair,
) -> None:
    """to_auth_ctx() must include identities from the storage backend.

    An empty auth_ctx.identities means X-DataRobot-Authorization-Context
    carries no identity data, breaking downstream agent token resolution.
    """
    loaded = await seeded_repos.user_repo.get_user(user_id=seeded_repos.user_id)

    assert loaded is not None
    auth_ctx = loaded.to_auth_ctx()
    assert len(auth_ctx.identities) == 1, (
        "to_auth_ctx().identities is empty — "
        "X-DataRobot-Authorization-Context will carry no identity data"
    )
