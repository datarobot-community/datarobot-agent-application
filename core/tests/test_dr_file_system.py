# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for DRFileSystem write-path legacy-probe caching."""

from typing import Any
from unittest.mock import Mock

import pytest
from datarobot.enums import FilesOverwriteStrategy
from datarobot.fs.file_system import DataRobotFileSystem

from core.persistent_fs.dr_file_system import DRFileSystem


class _FakeHandle:
    """Minimal stand-in for the DataRobotFile returned by super()._open('wb')."""

    def __init__(self) -> None:
        self.uploads = 0

    def _upload_chunk(self, final: bool = False) -> bool:
        self.uploads += 1
        return True


def _make_fs(legacy: Mock) -> DRFileSystem:
    """Build a DRFileSystem without its network-touching __init__."""
    fs = object.__new__(DRFileSystem)
    fs._paths_absent_from_legacy = set()
    fs.default_overwrite_strategy = FilesOverwriteStrategy.REPLACE
    fs._legacy_fs = legacy  # type: ignore[attr-defined]
    return fs


def test_open_write_probes_legacy_once_when_absent(monkeypatch: Any) -> None:
    legacy = Mock()
    legacy.exists.return_value = False
    legacy.isfile.return_value = False
    fs = _make_fs(legacy)

    handle = _FakeHandle()
    monkeypatch.setattr(
        DataRobotFileSystem,
        "_open",
        lambda self, path, mode="rb", **kw: handle,
    )

    for _ in range(5):
        fs._open("dr://cat/database.sqlite", mode="wb")

    # The legacy existence probe (a KeyValue-backed call) runs only on the first
    # write; later writes to the same path use the cached absence.
    assert legacy.exists.call_count == 1
    assert legacy.isfile.call_count <= 1


def test_open_write_migrates_then_caches_absence(monkeypatch: Any) -> None:
    legacy = Mock()
    # A legacy copy exists on the first write, so it must be probed and, after a
    # successful upload, removed (migration on write).
    legacy.exists.return_value = True
    legacy.isfile.return_value = True
    fs = _make_fs(legacy)

    handle = _FakeHandle()
    monkeypatch.setattr(
        DataRobotFileSystem,
        "_open",
        lambda self, path, mode="rb", **kw: handle,
    )

    # First write: probe + upload + delete legacy copy.
    fs._open("dr://cat/database.sqlite", mode="wb")
    handle._upload_chunk(final=True)
    assert legacy.rm_file.call_count == 1
    assert legacy.exists.call_count == 1

    # Second write: the path is now known absent from legacy, so no re-probe.
    handle2 = _FakeHandle()
    monkeypatch.setattr(
        DataRobotFileSystem,
        "_open",
        lambda self, path, mode="rb", **kw: handle2,
    )
    fs._open("dr://cat/database.sqlite", mode="wb")
    handle2._upload_chunk(final=True)
    assert legacy.exists.call_count == 1  # unchanged
    assert legacy.rm_file.call_count == 1  # not deleted again


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
