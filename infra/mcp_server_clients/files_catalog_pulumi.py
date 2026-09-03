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

"""Pulumi dynamic resource for Files API source bundles (catalog upload)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pulumi.dynamic import (
    CreateResult,
    DiffResult,
    Resource,
    ResourceProvider,
)

from .credentials import datarobot_api_token
from .files_api_client import FilesApiClient


def source_bundle_hash(files: list[tuple[str, str]]) -> str:
    """Content hash for a list of (absolute_path, relative_path) entries."""
    digest = hashlib.sha256()
    for abs_path, rel_path in sorted(files, key=lambda item: item[1]):
        digest.update(rel_path.encode())
        digest.update(Path(abs_path).read_bytes())
    return digest.hexdigest()


def read_bundle_files(files: list[tuple[str, str]]) -> list[tuple[str, bytes]]:
    return [(rel_path, Path(abs_path).read_bytes()) for abs_path, rel_path in files]


class FilesCatalogBundleProvider(ResourceProvider):
    # Any tracked change replaces the catalog (create new + delete old), so no
    # update() is implemented.

    def create(self, inputs: dict[str, Any]) -> CreateResult:
        client = FilesApiClient(
            endpoint=inputs["files_api_endpoint"],
            token=datarobot_api_token(),
        )
        bundle = read_bundle_files(inputs["source_files"])
        catalog_id, catalog_version_id = client.upload_bundle(bundle)
        outs = {
            **inputs,
            "catalog_id": catalog_id,
            "catalog_version_id": catalog_version_id,
        }
        return CreateResult(id_=catalog_id, outs=outs)

    def diff(self, _id: str, olds: dict[str, Any], news: dict[str, Any]) -> DiffResult:
        if olds.get("source_hash") != news.get("source_hash"):
            return DiffResult(changes=True, replaces=["*"])
        return DiffResult(changes=False)

    def delete(self, _id: str, props: dict[str, Any]) -> None:
        client = FilesApiClient(
            endpoint=props["files_api_endpoint"],
            token=datarobot_api_token(),
        )
        client.delete_catalog(_id)


class FilesCatalogBundle(Resource):
    """Uploads an application source bundle to the Files API and tracks catalog IDs in state."""

    catalog_id: str
    catalog_version_id: str

    def __init__(
        self,
        name: str,
        *,
        files_api_endpoint: str,
        source_files: list[tuple[str, str]],
        source_hash: str,
        opts: Any = None,
    ) -> None:
        super().__init__(
            FilesCatalogBundleProvider(),
            name,
            {
                "files_api_endpoint": files_api_endpoint,
                "source_files": source_files,
                "source_hash": source_hash,
                # outputs
                "catalog_id": None,
                "catalog_version_id": None,
            },
            opts,
        )
