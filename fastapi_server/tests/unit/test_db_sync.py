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
"""Unit tests for DBCtx remote-sync behaviour (request-scoped reuse + version guard)."""

import asyncio
import os
from asyncio import Lock
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel

from app.db import DBCtx, create_db_ctx


class FakeFS:
    """Stand-in for DRFileSystem that records calls and simulates a remote DB."""

    def __init__(self, db_path: str, version: str | None = "v1") -> None:
        self._db_path = db_path
        self.version = version
        self.download_calls = 0
        self.get_calls = 0
        self.put_calls = 0
        self.version_calls = 0

    def current_version_id(self) -> str | None:
        self.version_calls += 1
        return self.version

    def download_file(self, rpath: str, lpath: str) -> None:
        # Fast path: simulate a direct download of the latest version. Only
        # materialise bytes when the local file is absent so we don't clobber the
        # real SQLite DB the test engine is using (we assert on call counts).
        self.download_calls += 1
        if not os.path.exists(lpath):
            Path(lpath).write_bytes(b"remote-bytes")

    def get(self, rpath: str, lpath: str) -> None:
        # Fallback path (legacy filesystem); not expected in most tests.
        self.get_calls += 1
        if not os.path.exists(lpath):
            Path(lpath).write_bytes(b"remote-bytes")

    def put(self, lpath: str, rpath: str) -> None:
        self.put_calls += 1
        # An upload mints a new remote version.
        self.version = f"{self.version}-uploaded"


async def _make_ctx(tmp_path: Path) -> tuple[DBCtx, FakeFS]:
    db_file = tmp_path / "database.sqlite"
    ctx = await create_db_ctx(f"sqlite+aiosqlite:///{db_file}")
    async with ctx.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    fake = FakeFS(str(db_file))
    # Inject persistence as if _prepare_persistence_storage had wired a DRFileSystem.
    ctx._persistence_fs = fake  # type: ignore[assignment]
    ctx._db_path = str(db_file)
    ctx._lock = Lock()
    return ctx, fake


@pytest.fixture
async def ctx_and_fs(tmp_path: Path) -> tuple[DBCtx, FakeFS]:
    return await _make_ctx(tmp_path)


async def test_sync_scope_pulls_once_across_many_read_sessions(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs
    async with ctx.sync_scope():
        for _ in range(5):
            async with ctx.session() as sess:
                await sess.execute(text("SELECT 1"))

    # The DB is synced at most once per scope; later sessions do no remote work
    # at all (not even the cheap version check).
    assert fake.download_calls == 1
    assert fake.version_calls == 1


async def test_unchanged_version_skips_download(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    # First read with no local copy reflecting the remote -> downloads.
    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))
    assert fake.download_calls == 1

    # Subsequent reads (no scope): version unchanged + local present -> only the
    # cheap version check runs, no re-download.
    for _ in range(3):
        async with ctx.session() as sess:
            await sess.execute(text("SELECT 1"))
    assert fake.download_calls == 1
    assert fake.version_calls == 4


async def test_remote_version_advance_triggers_download(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))
    assert fake.download_calls == 1

    # Another writer advanced the remote version -> next read must re-download.
    fake.version = "v2"
    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))
    assert fake.download_calls == 2


async def test_download_falls_back_to_get_when_not_in_new_fs(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    # Simulate the file being absent from the new filesystem so the direct
    # download misses and we fall back to fsspec get() (legacy-aware).
    def _missing(rpath: str, lpath: str) -> None:
        fake.download_calls += 1
        raise FileNotFoundError(rpath)

    fake.download_file = _missing  # type: ignore[method-assign]

    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))

    assert fake.download_calls == 1
    assert fake.get_calls == 1


async def test_write_uploads_and_next_read_refreshes_advanced_remote(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    async with ctx.session(writable=True) as session:
        await session.execute(text("CREATE TABLE sync_probe (id INTEGER PRIMARY KEY)"))
        await ctx.commit(session)

    # The write changed the file -> uploaded exactly once. A later sync must not
    # blindly treat the local file as latest because another replica may also
    # have written after our upload.
    assert fake.put_calls == 1
    version_calls_after_write = fake.version_calls

    downloads_after_write = fake.download_calls
    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))
    # The later read observes a remote version advance and downloads it instead
    # of assuming the advance was authored locally.
    assert fake.download_calls == downloads_after_write + 1
    assert fake.version_calls == version_calls_after_write + 1
    assert ctx._pulled_version_id == fake.version  # "v1-uploaded"


async def test_remote_advance_after_local_upload_triggers_download(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    # Given a local write uploaded after pulling v1
    async with ctx.session(writable=True) as session:
        await session.execute(
            text("CREATE TABLE replica_probe (id INTEGER PRIMARY KEY)")
        )
        await ctx.commit(session)

    # When another replica advances the remote before this process reads again
    downloads_after_write = fake.download_calls
    fake.version = "v2-other-replica"
    async with ctx.session() as sess:
        await sess.execute(text("SELECT 1"))

    # Then the read downloads that newer version instead of marking local latest.
    assert fake.download_calls == downloads_after_write + 1
    assert ctx._pulled_version_id == "v2-other-replica"


async def test_sync_scope_coalesces_writes_into_one_upload(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    async with ctx.sync_scope():
        for i in range(3):
            async with ctx.session(writable=True) as session:
                await session.execute(
                    text(f"CREATE TABLE t{i} (id INTEGER PRIMARY KEY)")
                )
                await ctx.commit(session)
            # No upload happens mid-scope; it is deferred to scope exit.
            assert fake.put_calls == 0

    # Exactly one upload at scope exit captures the final DB state, regardless of
    # how many write sessions ran (#1). One pull check, and no post-put version
    # round-trip.
    assert fake.put_calls == 1
    assert fake.download_calls == 1
    assert fake.version_calls == 1


async def test_sync_scope_read_only_does_not_upload(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    async with ctx.sync_scope():
        for _ in range(3):
            async with ctx.session() as sess:
                await sess.execute(text("SELECT 1"))

    # A request that only reads never uploads.
    assert fake.put_calls == 0
    assert fake.download_calls == 1
    assert fake.version_calls == 1


async def test_sync_scope_coalesces_writes_from_background_task(
    ctx_and_fs: tuple[DBCtx, FakeFS],
) -> None:
    ctx, fake = ctx_and_fs

    async def write_in_task() -> None:
        async with ctx.session(writable=True) as session:
            await session.execute(text("CREATE TABLE bg (id INTEGER PRIMARY KEY)"))
            await ctx.commit(session)

    async with ctx.sync_scope():
        # The AG-UI storage consumer writes from a task spawned via
        # asyncio.create_task. Its writes must still be coalesced into the single
        # upload the parent scope performs on exit -- verifying the shared
        # scope-state object propagates across the task boundary.
        await asyncio.create_task(write_in_task())
        assert fake.put_calls == 0

    assert fake.put_calls == 1
