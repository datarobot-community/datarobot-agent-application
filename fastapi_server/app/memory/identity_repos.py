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
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from datarobot.models.memory import Session

from app.memory.constants import (
    IDENTITY_METADATA_VERSION,
    MEMORY_SPACE_MAX_RETRIEVAL_LIMIT,
    identity_by_user_provider_description,
)
from app.memory.identity_registry import IdentitySessionRegistry
from app.memory.locks import memory_space_lock
from app.memory.metadata_keys import session_metadata
from app.memory.repos import memory_space_participant_id
from app.users.identity import (
    AuthSchema,
    Identity,
    IdentityCreate,
    IdentityUpdate,
)

logger = logging.getLogger(__name__)


def _identity_session_participants(identity_uuid: UUID) -> list[str]:
    """Memory-service requires at least one participant when creating a session."""
    return [memory_space_participant_id(identity_uuid)]


def _synthetic_identity_id(identity_uuid: UUID) -> int:
    """Stable positive int id for API compatibility while users remain in SQLite."""
    digest = hashlib.sha256(identity_uuid.bytes).digest()
    value = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
    return value or 1


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _dt_to_wire(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def identity_to_metadata(identity: Identity) -> dict[str, Any]:
    assert identity.id is not None
    return {
        "v": IDENTITY_METADATA_VERSION,
        "identity_uuid": str(identity.uuid),
        "identity_id": identity.id,
        "user_id": identity.user_id,
        "type": identity.type.value,
        "provider_id": identity.provider_id,
        "provider_type": identity.provider_type,
        "provider_user_id": identity.provider_user_id,
        "provider_identity_id": identity.provider_identity_id,
        "access_token": identity.access_token,
        "access_token_expires_at": _dt_to_wire(identity.access_token_expires_at),
        "refresh_token": identity.refresh_token,
        "datarobot_org_id": identity.datarobot_org_id,
        "datarobot_tenant_id": identity.datarobot_tenant_id,
        "created_at": identity.created_at.isoformat(),
    }


def metadata_to_identity(session: Session) -> Identity | None:
    md = session_metadata(session)
    if md.get("v") != IDENTITY_METADATA_VERSION:
        return None
    try:
        identity_uuid = UUID(md["identity_uuid"])
        identity_id = int(md["identity_id"])
        user_id = int(md["user_id"])
        auth_type = AuthSchema(md["type"])
    except (KeyError, TypeError, ValueError):
        return None

    created_at = _parse_dt(md.get("created_at")) or (
        session.created_at or datetime.now(timezone.utc)
    )

    return Identity(
        id=identity_id,
        uuid=identity_uuid,
        created_at=created_at,
        type=auth_type,
        user_id=user_id,
        provider_id=md.get("provider_id") or "",
        provider_type=str(md["provider_type"]),
        provider_user_id=str(md["provider_user_id"]),
        provider_identity_id=md.get("provider_identity_id"),
        access_token=md.get("access_token"),
        access_token_expires_at=_parse_dt(md.get("access_token_expires_at")),
        refresh_token=md.get("refresh_token"),
        datarobot_org_id=md.get("datarobot_org_id"),
        datarobot_tenant_id=md.get("datarobot_tenant_id"),
    )


class MemoryIdentityRepository:
    """Identity persistence backed by memory-service sessions (metadata document per identity)."""

    def __init__(self, memory_space_id: str, registry: IdentitySessionRegistry) -> None:
        self._memory_space_id = memory_space_id
        self._registry = registry

    async def _iter_sessions(self) -> AsyncIterator[Session]:
        offset = 0
        page_size = MEMORY_SPACE_MAX_RETRIEVAL_LIMIT
        while True:

            def _list_page(o: int, lim: int) -> list[Session]:
                capped = min(lim, MEMORY_SPACE_MAX_RETRIEVAL_LIMIT)
                return Session.list(self._memory_space_id, offset=o, limit=capped)

            batch = await asyncio.to_thread(_list_page, offset, page_size)
            if not batch:
                break
            for s in batch:
                yield s
            offset += len(batch)

    def _session_to_identity(self, session: Session) -> Identity:
        identity = metadata_to_identity(session)
        if identity is None:
            raise ValueError("Memory session is missing valid identity metadata")
        assert identity.id is not None
        self._registry.register(
            session_id=session.id or "",
            user_id=identity.user_id,
            provider_type=identity.provider_type,
            provider_user_id=identity.provider_user_id,
            identity_uuid=identity.uuid,
            identity_id=identity.id,
        )
        return identity

    async def _get_session_by_user_provider(
        self, user_id: int, provider_type: str
    ) -> Session | None:
        sid = await self._registry.resolve_by_user_provider(user_id, provider_type)
        if not sid:
            return None

        def _get() -> Session:
            return Session.get(self._memory_space_id, sid)

        return await asyncio.to_thread(_get)

    async def create_identity(self, identity_data: IdentityCreate) -> Identity:
        lock_key = (
            f"{self._memory_space_id}:identity:"
            f"{identity_data.user_id}:{identity_data.provider_type}:"
            f"{identity_data.provider_user_id}"
        )
        async with memory_space_lock(lock_key):
            existing = await self.get_by_user_id(
                identity_data.provider_type, identity_data.user_id
            )
            if existing is not None:
                return existing

            identity_uuid = uuid4()
            identity_id = _synthetic_identity_id(identity_uuid)
            identity = Identity(
                id=identity_id,
                uuid=identity_uuid,
                created_at=datetime.now(timezone.utc),
                **identity_data.model_dump(),
            )
            metadata = identity_to_metadata(identity)
            description = identity_by_user_provider_description(
                identity.user_id, identity.provider_type
            )

            def _create() -> Session:
                return Session.create(
                    self._memory_space_id,
                    _identity_session_participants(identity.uuid),
                    metadata=metadata,
                    description=description,
                )

            session = await asyncio.to_thread(_create)
            if session.id is None:
                raise ValueError("Memory service returned a session without id")
            self._registry.register(
                session_id=session.id,
                user_id=identity.user_id,
                provider_type=identity.provider_type,
                provider_user_id=identity.provider_user_id,
                identity_uuid=identity.uuid,
                identity_id=identity_id,
            )
            return self._session_to_identity(session)

    async def get_identity_by_id(
        self,
        identity_id: int | None = None,
        identity_uuid: UUID | None = None,
    ) -> Identity | None:
        if identity_id is None and identity_uuid is None:
            raise ValueError("Either identity_id or identity_uuid must be provided.")

        if identity_uuid is not None:
            sid = await self._registry.resolve_by_uuid(identity_uuid)
        else:
            assert identity_id is not None
            sid = await self._registry.resolve_by_id(identity_id)

        if not sid:
            return None

        def _get() -> Session:
            return Session.get(self._memory_space_id, sid)

        session = await asyncio.to_thread(_get)
        return metadata_to_identity(session)

    async def get_by_user_id(self, provider_type: str, user_id: int) -> Identity | None:
        sid = await self._registry.resolve_by_user_provider(user_id, provider_type)
        if not sid:
            return None

        def _get() -> Session:
            return Session.get(self._memory_space_id, sid)

        session = await asyncio.to_thread(_get)
        return metadata_to_identity(session)

    async def get_by_external_user_id(
        self,
        provider_type: str,
        provider_user_id: str,
        auth_type: AuthSchema = AuthSchema.OAUTH2,
    ) -> Identity | None:
        sid = await self._registry.resolve_by_provider(provider_type, provider_user_id)
        if not sid:
            return None

        def _get() -> Session:
            return Session.get(self._memory_space_id, sid)

        session = await asyncio.to_thread(_get)
        identity = metadata_to_identity(session)
        if identity is None or identity.type != auth_type:
            return None
        return identity

    async def upsert_identity(
        self,
        user_id: int,
        auth_type: AuthSchema,
        provider_id: str,
        provider_type: str,
        provider_user_id: str,
        update: IdentityUpdate | None = None,
    ) -> Identity:
        lock_key = (
            f"{self._memory_space_id}:identity:"
            f"{user_id}:{provider_type}:{provider_user_id}"
        )
        async with memory_space_lock(lock_key):
            session = await self._get_session_by_user_provider(user_id, provider_type)
            if session is None:
                identity_uuid = uuid4()
                identity_id = _synthetic_identity_id(identity_uuid)
                identity = Identity(
                    id=identity_id,
                    uuid=identity_uuid,
                    created_at=datetime.now(timezone.utc),
                    type=auth_type,
                    user_id=user_id,
                    provider_id=provider_id,
                    provider_type=provider_type,
                    provider_user_id=provider_user_id,
                    provider_identity_id=None,
                    access_token=None,
                    access_token_expires_at=None,
                    refresh_token=None,
                    datarobot_org_id=None,
                    datarobot_tenant_id=None,
                )
                if update:
                    for field, value in update.model_dump(exclude_unset=True).items():
                        if value is not None:
                            setattr(identity, field, value)

                metadata = identity_to_metadata(identity)
                description = identity_by_user_provider_description(
                    user_id, provider_type
                )

                def _create() -> Session:
                    return Session.create(
                        self._memory_space_id,
                        _identity_session_participants(identity_uuid),
                        metadata=metadata,
                        description=description,
                    )

                session = await asyncio.to_thread(_create)
                if session.id is None:
                    raise ValueError("Memory service returned a session without id")
                self._registry.register(
                    session_id=session.id,
                    user_id=user_id,
                    provider_type=provider_type,
                    provider_user_id=provider_user_id,
                    identity_uuid=identity.uuid,
                    identity_id=identity_id,
                )
                return self._session_to_identity(session)

            existing = metadata_to_identity(session)
            if existing is None:
                raise ValueError("Memory session is missing valid identity metadata")

            identity = existing
            identity.type = auth_type
            identity.user_id = user_id
            identity.provider_id = provider_id
            identity.provider_type = provider_type
            identity.provider_user_id = provider_user_id

            if update:
                for field, value in update.model_dump(exclude_unset=True).items():
                    if value is not None:
                        setattr(identity, field, value)

            metadata = identity_to_metadata(identity)
            description = identity_by_user_provider_description(user_id, provider_type)
            sid = session.id
            if sid is None:
                raise ValueError("Memory session is missing id")

            def _patch() -> Session:
                s = Session.get(self._memory_space_id, sid)
                s.update(metadata=metadata, description=description)
                return Session.get(self._memory_space_id, sid)

            updated = await asyncio.to_thread(_patch)
            return self._session_to_identity(updated)

    async def update_identity(
        self, identity_id: int, update: IdentityUpdate
    ) -> Identity | None:
        sid = await self._registry.resolve_by_id(identity_id)
        if not sid:
            return None

        def _patch() -> tuple[tuple[int, str, str, UUID, int] | None, Session | None]:
            s = Session.get(self._memory_space_id, sid)
            identity = metadata_to_identity(s)
            if identity is None or identity.id is None:
                return None, None
            old_keys = (
                identity.user_id,
                identity.provider_type,
                identity.provider_user_id,
                identity.uuid,
                identity.id,
            )
            for field, value in update.model_dump(exclude_unset=True).items():
                setattr(identity, field, value)
            s.update(metadata=identity_to_metadata(identity))
            refreshed = Session.get(self._memory_space_id, sid)
            return old_keys, refreshed

        old_keys, session = await asyncio.to_thread(_patch)
        if old_keys is None or session is None:
            return None

        old_user_id, old_provider_type, old_provider_user_id, old_uuid, old_id = (
            old_keys
        )
        updated = metadata_to_identity(session)
        if updated is None:
            return None
        if (
            old_user_id != updated.user_id
            or old_provider_type != updated.provider_type
            or old_provider_user_id != updated.provider_user_id
        ):
            self._registry.unregister(
                user_id=old_user_id,
                provider_type=old_provider_type,
                provider_user_id=old_provider_user_id,
                identity_uuid=old_uuid,
                identity_id=old_id,
            )
        return self._session_to_identity(session)

    async def list_by_user_id(self, user_id: int) -> list[Identity]:
        identities: list[Identity] = []
        async for session in self._iter_sessions():
            identity = metadata_to_identity(session)
            if identity is None or identity.user_id != user_id:
                continue
            identities.append(identity)
        return identities

    async def delete_by_id(self, identity_id: int) -> None:
        sid = await self._registry.resolve_by_id(identity_id)
        if not sid:
            return

        def _delete() -> None:
            s = Session.get(self._memory_space_id, sid)
            identity = metadata_to_identity(s)
            s.delete()
            if identity is not None and identity.id is not None:
                self._registry.unregister(
                    user_id=identity.user_id,
                    provider_type=identity.provider_type,
                    provider_user_id=identity.provider_user_id,
                    identity_uuid=identity.uuid,
                    identity_id=identity.id,
                )

        await asyncio.to_thread(_delete)

    async def delete_by_user_id(self, user_id: int) -> None:
        to_delete: list[tuple[str, int, str, str, UUID, int]] = []

        async for session in self._iter_sessions():
            identity = metadata_to_identity(session)
            if identity is None or identity.user_id != user_id:
                continue
            if session.id is None or identity.id is None:
                continue
            to_delete.append(
                (
                    session.id,
                    identity.user_id,
                    identity.provider_type,
                    identity.provider_user_id,
                    identity.uuid,
                    identity.id,
                )
            )

        def _delete_all() -> None:
            for (
                sid,
                identity_user_id,
                provider_type,
                provider_user_id,
                identity_uuid,
                identity_id,
            ) in to_delete:
                Session.get(self._memory_space_id, sid).delete()
                self._registry.unregister(
                    user_id=identity_user_id,
                    provider_type=provider_type,
                    provider_user_id=provider_user_id,
                    identity_uuid=identity_uuid,
                    identity_id=identity_id,
                )

        await asyncio.to_thread(_delete_all)
