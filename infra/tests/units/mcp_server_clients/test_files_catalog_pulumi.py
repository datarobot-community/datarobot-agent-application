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

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from mcp_server_clients.files_catalog_pulumi import (
    FilesCatalogBundleProvider,
    read_bundle_files,
    source_bundle_hash,
)

# Bound to a name so patch targets stay a fixed width: this file is a copier
# template and the package prefix varies in length with the user's app name,
# which otherwise makes `ruff format --check` pass or fail per rendered name.
MODULE = "mcp_server_clients.files_catalog_pulumi"


@contextmanager
def env(**variables: str | None):
    originals = {name: os.environ.get(name) for name in variables}
    try:
        for name, value in variables.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, original in originals.items():
            if original is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = original


class TestSourceBundleHash:
    def test_source_bundle_hash_same_regardless_of_input_order(self, tmp_path) -> None:
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_text("alpha", encoding="utf-8")
        file_b.write_text("beta", encoding="utf-8")
        files = [(str(file_b), "b.txt"), (str(file_a), "a.txt")]
        actual = source_bundle_hash(files)
        expected = source_bundle_hash(list(reversed(files)))
        assert actual == expected

    def test_source_bundle_hash_changes_when_file_content_changes(
        self, tmp_path
    ) -> None:
        path = tmp_path / "app.py"
        path.write_text("v1", encoding="utf-8")
        first = source_bundle_hash([(str(path), "app.py")])
        path.write_text("v2", encoding="utf-8")
        actual = source_bundle_hash([(str(path), "app.py")])
        expected = first
        assert actual != expected


class TestReadBundleFiles:
    def test_read_bundle_files_reads_relative_path_and_bytes(self, tmp_path) -> None:
        path = tmp_path / "app.py"
        path.write_bytes(b"print('hi')")
        actual = read_bundle_files([(str(path), "app.py")])
        expected = [("app.py", b"print('hi')")]
        assert actual == expected


class TestFilesCatalogBundleProvider:
    def test_diff_replaces_when_source_hash_changes(self) -> None:
        provider = FilesCatalogBundleProvider()
        actual = provider.diff("id", {"source_hash": "a"}, {"source_hash": "b"}).changes
        expected = True
        assert actual == expected

    def test_diff_no_changes_when_source_hash_matches(self) -> None:
        provider = FilesCatalogBundleProvider()
        actual = provider.diff(
            "id", {"source_hash": "same"}, {"source_hash": "same"}
        ).changes
        expected = False
        assert actual == expected

    def test_create_uploads_bundle_and_returns_catalog_ids(self) -> None:
        provider = FilesCatalogBundleProvider()
        inputs = {
            "files_api_endpoint": "https://api.example.com",
            "source_files": [("/tmp/app.py", "app.py")],
            "source_hash": "hash",
        }
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                f"{MODULE}.read_bundle_files",
                return_value=[("app.py", b"code")],
            ),
            patch(f"{MODULE}.FilesApiClient") as client_cls,
        ):
            client_cls.return_value.upload_bundle.return_value = ("cat", "ver")
            result = provider.create(inputs)
        assert result.outs is not None
        actual = (
            result.id,
            result.outs["catalog_id"],
            result.outs["catalog_version_id"],
        )
        expected = ("cat", "cat", "ver")
        assert actual == expected

    def test_delete_deletes_catalog_by_id(self) -> None:
        provider = FilesCatalogBundleProvider()
        props = {"files_api_endpoint": "https://api.example.com"}
        mock_client = MagicMock()
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                f"{MODULE}.FilesApiClient",
                return_value=mock_client,
            ),
        ):
            provider.delete("cat-1", props)
        actual = mock_client.delete_catalog.call_args.args[0]
        expected = "cat-1"
        assert actual == expected
