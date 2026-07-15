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

import asyncio
import logging
import os
from asyncio import Lock
from contextlib import nullcontext

import datarobot as dr
from datarobot.enums import KeyValueEntityType as DRKeyValueEntityType
from datarobot.models.files import Files
from fastapi import APIRouter, Request

from alembic_migration import run_alembic_upgrade
from app.db import create_db_ctx
from core.persistent_fs.dr_file_system import (
    CATALOG_STORAGE_NAME,
    METADATA_STORAGE_NAME,
    TIMESTAMP_STORAGE_NAME,
    DRFileSystem,
)

logger = logging.getLogger(__name__)
dev_router = APIRouter(tags=["Dev"])


def _delete_remote_storage(fs: DRFileSystem) -> None:
    """Delete the remote file catalog container and all related KV entries."""
    app_id = fs.app_id

    with fs.client:
        if fs._catalog_id:
            try:
                Files.delete(fs._catalog_id)
                logger.info("Deleted remote catalog container %s", fs._catalog_id)
            except Exception:
                logger.warning(
                    "Failed to delete catalog %s", fs._catalog_id, exc_info=True
                )

        if app_id:
            for kv_name in [
                CATALOG_STORAGE_NAME,
                METADATA_STORAGE_NAME,
                TIMESTAMP_STORAGE_NAME,
            ]:
                try:
                    kv = dr.KeyValue.find(
                        app_id, DRKeyValueEntityType.CUSTOM_APPLICATION, kv_name
                    )
                    if kv:
                        kv.delete()
                        logger.info("Deleted KV entry '%s'", kv_name)
                except Exception:
                    logger.warning(
                        "Failed to delete KV entry '%s'", kv_name, exc_info=True
                    )


@dev_router.post("/dev/reset-db")
async def reset_db(request: Request) -> dict[str, str]:
    """
    Delete the local SQLite file, the remote file catalog, and all related KV
    entries, then reinitialize the database with a fresh schema.

    Only registered when TEST_USER_EMAIL is set.
    """
    deps = request.app.state.deps
    db = deps.db
    config = deps.config

    # 1. Delete local sqlite file
    if db._db_path and os.path.exists(db._db_path):
        os.remove(db._db_path)
        logger.info("Deleted local sqlite at %s", db._db_path)

    # 2. Delete remote file catalog and KV entries
    if db._persistence_fs:
        await asyncio.to_thread(_delete_remote_storage, db._persistence_fs)

    # 3. Reinitialize the database engine in-place so all existing repo
    #    references (which hold a reference to this same DBCtx object) pick
    #    up the fresh engine automatically. create_db_ctx also re-creates
    #    the remote catalog + KV if APPLICATION_ID is configured.
    await db.engine.dispose()
    new_db = await create_db_ctx(config.database_uri)
    db.engine = new_db.engine
    db._session = new_db._session
    db._pulled_version_id = None
    db._persistence_fs = new_db._persistence_fs
    db._db_path = new_db._db_path
    db._lock = Lock() if new_db._persistence_fs else nullcontext()

    # 4. Recreate the schema via alembic migrations against the empty database
    await asyncio.to_thread(run_alembic_upgrade, True)

    return {"status": "ok"}
