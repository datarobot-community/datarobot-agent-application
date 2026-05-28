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

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from datarobot.models.memory import Session
from sqlalchemy.exc import IntegrityError

from app.memory.constants import USER_METADATA_VERSION, user_by_email_description
from app.memory.locks import memory_space_lock
from app.memory.metadata_keys import session_metadata
from app.memory.repos import memory_space_participant_id
from app.memory.user_attachments import UserIdentitySource, attach_user_identities
from app.memory.user_registry import UserSessionRegistry
from app.users.user import LanguageEnum, ThemeEnum, User, UserCreate

logger = logging.getLogger(__name__)


def _user_session_participants(user_uuid: UUID) -> list[str]:
    """Memory-service requires at least one participant when creating a session."""
    return [memory_space_participant_id(user_uuid)]


def _synthetic_user_id(user_uuid: UUID) -> int:
    """Stable positive int id for API compatibility with auth session user ids."""
    digest = hashlib.sha256(user_uuid.bytes).digest()
    value = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
    return value or 1


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def user_to_metadata(user: User) -> dict[str, Any]:
    assert user.id is not None
    return {
        "v": USER_METADATA_VERSION,
        "user_uuid": str(user.uuid),
        "user_id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "profile_image_url": user.profile_image_url,
        "theme": user.theme.value,
        "language": user.language.value,
        "created_at": user.created_at.isoformat(),
    }


def metadata_to_user(session: Session) -> User | None:
    md = session_metadata(session)
    if md.get("v") != USER_METADATA_VERSION:
        return None
    try:
        user_uuid = UUID(md["user_uuid"])
        user_id = int(md["user_id"])
        email = str(md["email"])
        theme = ThemeEnum(md["theme"])
        language = LanguageEnum(md["language"])
    except (KeyError, TypeError, ValueError):
        return None

    created_at = _parse_dt(md.get("created_at")) or (
        session.created_at or datetime.now(timezone.utc)
    )

    return User(
        id=user_id,
        uuid=user_uuid,
        created_at=created_at,
        email=email,
        first_name=md.get("first_name"),
        last_name=md.get("last_name"),
        profile_image_url=md.get("profile_image_url"),
        theme=theme,
        language=language,
        identities=[],
    )


class MemoryUserRepository:
    """User persistence backed by memory-service sessions (metadata document per user)."""

    def __init__(
        self,
        memory_space_id: str,
        registry: UserSessionRegistry,
        identity_repo: UserIdentitySource,
    ) -> None:
        self._memory_space_id = memory_space_id
        self._registry = registry
        self._identity_repo = identity_repo

    def _session_to_user(self, session: Session) -> User:
        user = metadata_to_user(session)
        if user is None:
            raise ValueError("Memory session is missing valid user metadata")
        assert user.id is not None
        self._registry.register(
            session_id=session.id or "",
            email=user.email,
            user_uuid=user.uuid,
            user_id=user.id,
        )
        return user

    async def get_user(
        self,
        user_id: int | None = None,
        user_uuid: UUID | None = None,
        email: str | None = None,
    ) -> User | None:
        if user_id is None and user_uuid is None and email is None:
            raise ValueError("Either user_id, user_uuid, or email must be provided.")

        if email is not None:
            sid = await self._registry.resolve_by_email(email)
        elif user_uuid is not None:
            sid = await self._registry.resolve_by_uuid(user_uuid)
        else:
            assert user_id is not None
            sid = await self._registry.resolve_by_id(user_id)

        if not sid:
            return None

        def _get() -> Session:
            return Session.get(self._memory_space_id, sid)

        session = await asyncio.to_thread(_get)
        user = metadata_to_user(session)
        return await attach_user_identities(user, self._identity_repo)

    async def create_user(self, user_data: UserCreate) -> User:
        lock_key = f"{self._memory_space_id}:user:email:{user_data.email}"
        async with memory_space_lock(lock_key):
            existing = await self.get_user(email=user_data.email)
            if existing is not None:
                raise IntegrityError(
                    "duplicate user email",
                    {},
                    Exception("duplicate user email"),
                )

            user_uuid = uuid4()
            user_id = _synthetic_user_id(user_uuid)
            user = User(
                id=user_id,
                uuid=user_uuid,
                created_at=datetime.now(timezone.utc),
                **user_data.model_dump(),
                identities=[],
            )
            metadata = user_to_metadata(user)
            description = user_by_email_description(user.email)

            def _create() -> Session:
                return Session.create(
                    self._memory_space_id,
                    _user_session_participants(user.uuid),
                    metadata=metadata,
                    description=description,
                )

            session = await asyncio.to_thread(_create)
            if session.id is None:
                raise ValueError("Memory service returned a session without id")
            self._registry.register(
                session_id=session.id,
                email=user.email,
                user_uuid=user.uuid,
                user_id=user_id,
            )
            user = self._session_to_user(session)
            attached = await attach_user_identities(user, self._identity_repo)
            assert attached is not None
            return attached

    async def update_user_settings(
        self,
        user_id: int,
        theme: ThemeEnum | None = None,
        language: LanguageEnum | None = None,
    ) -> User:
        sid = await self._registry.resolve_by_id(user_id)
        if not sid:
            raise ValueError(f"User with id {user_id} not found")

        def _patch() -> Session:
            s = Session.get(self._memory_space_id, sid)
            user = metadata_to_user(s)
            if user is None:
                raise ValueError(f"User with id {user_id} not found")
            if theme is not None:
                user.theme = theme
            if language is not None:
                user.language = language
            s.update(metadata=user_to_metadata(user))
            return Session.get(self._memory_space_id, sid)

        updated = await asyncio.to_thread(_patch)
        user = self._session_to_user(updated)
        attached = await attach_user_identities(user, self._identity_repo)
        assert attached is not None
        return attached
