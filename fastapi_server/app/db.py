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

import logging
import os
from asyncio import Lock
from contextlib import asynccontextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from typing import AsyncGenerator, cast

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import UOWTransaction
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from core.persistent_fs.dr_file_system import (
    DRFileSystem,
    all_env_variables_present,
    calculate_checksum,
)

logger = logging.getLogger()


def _prepare_persistence_storage(
    engine: AsyncEngine,
) -> tuple[DRFileSystem, str] | tuple[None, None]:
    if not all_env_variables_present():
        return None, None

    if "sqlite" not in engine.url.drivername:
        return None, None
    if not engine.url.database or ":memory:" == engine.url.database:
        return None, None

    file_path = engine.url.database
    persistent_fs = DRFileSystem()
    return persistent_fs, file_path


@dataclass
class _SyncScopeState:
    """Per-``sync_scope()`` state shared across the request task and any
    background tasks it spawns.

    A mutable object is stored in a single ``ContextVar`` (rather than plain
    bool ContextVars) so that state set inside a child task -- e.g. the AG-UI
    storage consumer created via ``asyncio.create_task`` -- is visible when the
    scope exits in the parent task. ``asyncio.create_task`` copies the context,
    so child tasks inherit the *same* object reference and mutate it in place.
    """

    # The remote DB has been pulled at least once within this scope.
    pulled: bool = False
    # Checksum of the local DB captured before the first write in this scope.
    # Only set once ``baseline_captured`` is True. Used at scope exit to decide
    # whether a single coalesced upload is required.
    baseline_captured: bool = False
    baseline_checksum: bytes | None = None


class DBCtx:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

        self._session = async_sessionmaker(
            autoflush=False,
            class_=AsyncSession,
            bind=engine,
            expire_on_commit=False,
        )

        self._persistence_fs: DRFileSystem | None
        self._db_path: str | None
        self._persistence_fs, self._db_path = _prepare_persistence_storage(engine)

        self._lock: Lock | nullcontext = nullcontext()  # type: ignore[type-arg]
        if self._persistence_fs:
            self._lock = Lock()

        # Session shared by all `session()` calls within an open `session_scope()`
        # in the current task context (e.g. the AG-UI storage consumer batches).
        self._scoped_session: ContextVar[AsyncSession | None] = ContextVar(
            "dbctx_scoped_session", default=None
        )

        # Within an open `sync_scope()` (e.g. one HTTP request) the persistent DB
        # is pulled from remote storage at most once and uploaded at most once.
        # Without an active scope every session re-pulls and uploads on change,
        # which is the legacy behaviour.
        self._sync_scope: ContextVar[_SyncScopeState | None] = ContextVar(
            "dbctx_sync_scope", default=None
        )

        # Catalog version id of the remote DB the local copy reflects. Used to
        # skip downloads only when the remote has not changed since our last
        # pull. Uploads do not update this value because a later version check
        # cannot safely distinguish our write from another replica's write.
        self._pulled_version_id: str | None = None

    def _current_checksum(self) -> bytes | None:
        """Checksum of the local DB file, or None if it does not exist yet."""
        db_path = cast(str, self._db_path)
        if os.path.exists(db_path):
            return calculate_checksum(db_path)
        return None

    def _pull_db_if_needed(self) -> None:
        """Sync the local DB from remote storage when needed.

        Skips work entirely when an active `sync_scope()` has already synced once
        in this context. Otherwise performs a cheap remote version check and only
        downloads when the catalog version has advanced since our last pull (or
        when there is no local copy yet).
        """
        if not self._persistence_fs:
            return
        state = self._sync_scope.get()
        if state is not None and state.pulled:
            return

        self._sync_db_from_remote()

        if state is not None:
            state.pulled = True

    def _sync_db_from_remote(self) -> None:
        db_path = cast(str, self._db_path)
        fs = self._persistence_fs
        if fs is None:
            return

        remote_version = fs.current_version_id()
        local_exists = os.path.exists(db_path)
        if (
            local_exists
            and remote_version is not None
            and remote_version == self._pulled_version_id
        ):
            # Local copy already reflects the latest remote version.
            return

        try:
            # Stream the latest version of the known file in a single request.
            # Falls back to fsspec get() (which also consults the legacy
            # filesystem) if the file is not in the new filesystem.
            try:
                fs.download_file(db_path, db_path)
            except FileNotFoundError:
                fs.get(db_path, db_path)
        except FileNotFoundError:
            return
        self._pulled_version_id = remote_version

    async def _flush_scope_upload(self, state: _SyncScopeState) -> None:
        """Upload the DB once at `sync_scope()` exit if a write changed it.

        Coalesces the many write sessions of a single request (e.g. every
        streamed-event batch) into one upload of the final DB state instead of
        one upload per write session.
        """
        if not self._persistence_fs or not state.baseline_captured:
            return
        async with self._lock:
            db_path = cast(str, self._db_path)
            if not os.path.exists(db_path):
                return
            if self._current_checksum() == state.baseline_checksum:
                return
            self._persistence_fs.put(db_path, db_path)

    @asynccontextmanager
    async def sync_scope(self) -> AsyncGenerator[None, None]:
        """
        Mark a logical scope (typically one HTTP request) during which the
        persistent DB is fetched from remote storage at most once, shared by
        every `session()` opened within it, and uploaded at most once (on exit)
        if any write changed it. Outside a scope each session re-pulls and each
        write uploads on change.
        """
        if not self._persistence_fs:
            yield
            return

        state = _SyncScopeState()
        token = self._sync_scope.set(state)
        try:
            yield
        finally:
            self._sync_scope.reset(token)
            await self._flush_scope_upload(state)

    @asynccontextmanager
    async def _read_session(self) -> AsyncGenerator[AsyncSession, None]:
        def prevent_writes(
            session_: AsyncSession, flush_context: UOWTransaction, instances: None
        ) -> None:
            if session_.dirty or session_.new or session_.deleted:
                raise RuntimeError(
                    "This session is read-only and cannot perform writes."
                )

        self._pull_db_if_needed()

        async with self._session() as session:
            event.listen(session.sync_session, "before_flush", prevent_writes)
            yield session

    @asynccontextmanager
    async def _write_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._lock:
            self._pull_db_if_needed()
            state = self._sync_scope.get()

            baseline: bytes | None = None
            if self._persistence_fs:
                if state is not None:
                    # Capture the pre-write baseline once for the whole scope; the
                    # actual upload is deferred to sync_scope exit so a burst of
                    # write sessions collapses into a single upload.
                    if not state.baseline_captured:
                        state.baseline_checksum = self._current_checksum()
                        state.baseline_captured = True
                else:
                    baseline = self._current_checksum()

            async with self._session() as session:
                yield session

            if not self._persistence_fs or state is not None:
                # No persistence, or coalesced: nothing to upload here.
                return

            # No active scope (legacy path): upload immediately on change.
            if self._current_checksum() != baseline:
                db_path = cast(str, self._db_path)
                self._persistence_fs.put(db_path, db_path)

    @asynccontextmanager
    async def session(
        self, writable: bool = False
    ) -> AsyncGenerator[AsyncSession, None]:
        if scoped_session := self._scoped_session.get():
            yield scoped_session
            return

        session_context = self._write_session if writable else self._read_session
        async with session_context() as session:
            yield session

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Open a single writable session shared by every `session()` call made within
        this scope in the current task. `commit()` calls against the shared session
        become flushes; the one real commit happens on scope exit. This keeps bursts
        of repository calls (e.g. streaming event persistence) on one connection,
        one transaction, and one persistence sync instead of one of each per call.
        """
        if self._scoped_session.get():
            raise RuntimeError("session_scope cannot be nested.")

        async with self._write_session() as session:
            token = self._scoped_session.set(session)
            try:
                yield session
                await session.commit()
            finally:
                self._scoped_session.reset(token)

    async def commit(self, session: AsyncSession) -> None:
        """
        Commit the session, unless it is the shared session of an open
        `session_scope()` — then flush so the scope owner commits once at exit.
        """
        if self._scoped_session.get() is session:
            await session.flush()
            return
        await session.commit()

    async def shutdown(self) -> None:
        """
        Dispose of the engine and close all pooled connections.
        Call this on application shutdown.
        """
        await self.engine.dispose()


class DBSyncScopeMiddleware:
    """ASGI middleware that opens a :meth:`DBCtx.sync_scope` around each HTTP
    request so the persistent DB is pulled from remote storage at most once per
    request instead of once per repository call.

    Relies on ``scope["app"].state.deps.db`` being a :class:`DBCtx`. If deps are
    not yet wired (e.g. before startup completes) the request passes through
    untouched, preserving the legacy per-session pull behaviour.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        deps = getattr(getattr(scope.get("app"), "state", None), "deps", None)
        db = getattr(deps, "db", None)
        if not isinstance(db, DBCtx):
            await self.app(scope, receive, send)
            return

        async with db.sync_scope():
            await self.app(scope, receive, send)


async def create_db_ctx(db_url: str, log_sql_stmts: bool = False) -> DBCtx:
    async_engine = create_async_engine(
        db_url,
        echo=log_sql_stmts,
    )

    async with async_engine.begin() as conn:
        # testing DB credentials...
        await conn.execute(text("select '1'"))

    return DBCtx(async_engine)
