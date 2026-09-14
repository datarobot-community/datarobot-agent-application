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
from pathlib import Path
from unittest.mock import patch

import pulumi
import pytest

import infra as infra_dir
from infra.mcp_server_infra.mcp_bundle import (
    FileBundler,
    ensure_docker_build_context_files,
    get_docker_bundle_files,
    get_workload_source_files,
    merge_source_files,
    normalize_shell_scripts,
)
from infra.mcp_server_infra.workload import (
    GENERATED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS,
    PROVIDED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS,
)


def test_merge_source_files_keeps_last_duplicate_relative_path():
    merged = merge_source_files(
        [("/tmp/a", "requirements.txt"), ("/tmp/b", "app/main.py")],
        [("/tmp/c", "requirements.txt")],
    )

    assert merged == [("/tmp/b", "app/main.py"), ("/tmp/c", "requirements.txt")]


def test_get_workload_source_files_includes_docker_assets_when_using_provided_dockerfile(
    tmp_path: Path,
):
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)
    (deployments_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (deployments_path / "pyproject.toml").write_text("", encoding="utf-8")
    (deployments_path / "uv.lock").write_text("", encoding="utf-8")
    (deployments_path / "start_server.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    core_files = [("/tmp/app/main.py", "app/main.py")]

    files = get_workload_source_files(
        deployments_path=deployments_path,
        dockerfile_relative_path="Dockerfile",
        get_core_app_files=lambda: core_files,
    )

    rel_paths = {rel_path for _, rel_path in files}
    assert rel_paths == {"app/main.py", "Dockerfile"}


def test_get_workload_source_files_bundles_a_custom_dockerfile_path(tmp_path: Path):
    """MCP_WORKLOAD_DOCKERFILE_PATH must reach the bundle, not just the artifact spec.

    The build looks for the Dockerfile at the catalog-relative path in the spec,
    so uploading ``Dockerfile`` while the spec says ``custom/Dockerfile``
    fails the build.
    """
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)
    (deployments_path / "custom").mkdir(parents=True)
    (deployments_path / "custom" / "Dockerfile").write_text(
        "FROM scratch\n", encoding="utf-8"
    )
    (deployments_path / "pyproject.toml").write_text("", encoding="utf-8")
    (deployments_path / "uv.lock").write_text("", encoding="utf-8")
    (deployments_path / "start_server.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    files = get_workload_source_files(
        deployments_path=deployments_path,
        dockerfile_relative_path="custom/Dockerfile",
        get_core_app_files=list,
    )

    rel_paths = {rel_path for _, rel_path in files}
    assert rel_paths == {"custom/Dockerfile"}


def test_get_docker_bundle_files_error_names_the_configured_path(tmp_path: Path):
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)

    with (
        patch.object(pulumi, "error"),
        pytest.raises(RuntimeError, match="custom/Dockerfile"),
    ):
        get_docker_bundle_files(deployments_path, "custom/Dockerfile")


def test_get_workload_source_files_skips_docker_assets_for_generated_mode(
    tmp_path: Path,
):
    core_files = [("/tmp/app/main.py", "app/main.py")]

    files = get_workload_source_files(
        deployments_path=tmp_path,
        dockerfile_relative_path=None,
        get_core_app_files=lambda: core_files,
    )

    assert files == core_files


def test_get_docker_bundle_files_requires_pyproject_and_lock(tmp_path: Path):
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)
    (deployments_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    with (
        patch.object(pulumi, "error") as mock_error,
        pytest.raises(RuntimeError, match="pyproject.toml"),
    ):
        get_docker_bundle_files(deployments_path)

    mock_error.assert_called_once()


def test_ensure_docker_build_context_files_passes_when_all_present(tmp_path: Path):
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)
    (deployments_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (deployments_path / "pyproject.toml").write_text("content\n", encoding="utf-8")
    (deployments_path / "uv.lock").write_text("lock\n", encoding="utf-8")
    (deployments_path / "start_server.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    ensure_docker_build_context_files(deployments_path)


def test_ensure_docker_build_context_files_raises_when_missing(tmp_path: Path):
    deployments_path = tmp_path / "mcp_server"
    deployments_path.mkdir(parents=True)
    (deployments_path / "pyproject.toml").write_text("content\n", encoding="utf-8")

    with (
        patch.object(pulumi, "error") as mock_error,
        pytest.raises(RuntimeError, match="Dockerfile"),
    ):
        ensure_docker_build_context_files(deployments_path)

    mock_error.assert_called_once()


def test_normalize_shell_scripts_rewrites_crlf_to_lf(tmp_path: Path):
    script = tmp_path / "start_server.sh"
    script.write_bytes(b"if [ 1 ]; then\r\n  echo hi\r\nfi\r\n")
    bundle = [(str(script), "start_server.sh")]

    assert normalize_shell_scripts(bundle) == bundle

    assert script.read_bytes() == b"if [ 1 ]; then\n  echo hi\nfi\n"


def test_normalize_shell_scripts_leaves_other_files_alone(tmp_path: Path):
    module = tmp_path / "main.py"
    module.write_bytes(b"x = 1\r\n")

    normalize_shell_scripts([(str(module), "app/main.py")])

    assert module.read_bytes() == b"x = 1\r\n"


@contextmanager
def env(**variables: str | None):
    """Temporarily set or remove environment variables."""
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


class TestFileBundler:
    @pytest.fixture
    def project_dir(self):
        yield infra_dir.project_dir.parent

    @pytest.fixture
    def deployment_app_path(self, project_dir):
        yield project_dir / "mcp_server"

    def test_setup_build_dir_for_workload_artifact_source_dir_return(self, tmp_path):
        ignore_patterns = ["file.py"]
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        dockerfile_rel_path = "Dockerfile"
        dockerfile = source_dir / dockerfile_rel_path
        dockerfile.write_text("hi")
        build_dir = tmp_path / ".build"
        file_bundler = FileBundler(source_dir, project_dir_abs_path=tmp_path)

        actual = file_bundler.setup_build_dir_for_workload_artifact_source_dir(
            build_dir, ignore_patterns
        )

        expected = build_dir
        assert actual == expected
        assert build_dir.exists()

    def test_setup_build_dir_for_workload_artifact_source_dir__for_provided_dockerfile(
        self, tmp_path, deployment_app_path, project_dir
    ):
        file_bundler = FileBundler(deployment_app_path, project_dir)
        ignore_patterns = PROVIDED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS
        build_dir = tmp_path / ".build"

        file_bundler.setup_build_dir_for_workload_artifact_source_dir(
            build_dir, ignore_patterns
        )

        assert build_dir.exists()
        assert (build_dir / "app").exists()
        assert (build_dir / "start_server.sh").exists()
        assert (build_dir / "pyproject.toml").exists()
        assert (build_dir / "Dockerfile").exists()
        # no check for uv.lock because the base mcp template doesn't have one
        assert not (build_dir / ".dockerignore").exists()

    def test_setup_build_dir_for_workload_artifact_source_dir__for_generated_dockerfile(
        self, tmp_path, deployment_app_path, project_dir
    ):
        file_bundler = FileBundler(deployment_app_path, project_dir)
        build_dir = tmp_path
        ignore_patterns = GENERATED_DOCKERFILE_BUILD_DIR_IGNORE_PATTERNS

        file_bundler.setup_build_dir_for_workload_artifact_source_dir(
            build_dir, ignore_patterns
        )

        assert build_dir.exists()
        assert (build_dir / "app").exists()
        assert (build_dir / "start_server.sh").exists()
        assert (build_dir / "pyproject.toml").exists()
        # no check for uv.lock because the base mcp template doesn't have one
        assert not (build_dir / "Dockerfile").exists()
        assert not (build_dir / ".dockerignore").exists()

    @pytest.mark.parametrize("value", ["none", "false", "0", "NONE"])
    def test_resolve_dockerfile_relative_path__disabled_values_return_none(
        self, value: str, tmp_path
    ):
        with env(MCP_WORKLOAD_DOCKERFILE_PATH=value):
            actual = FileBundler.resolve_dockerfile_relative_path(tmp_path)

            expected = None
            assert actual == expected

    def test_resolve_dockerfile_relative_path__explicit_dockerfile_path(self, tmp_path):
        with env(MCP_WORKLOAD_DOCKERFILE_PATH="custom/Dockerfile"):
            actual = FileBundler.resolve_dockerfile_relative_path(tmp_path)

            expected = "custom/Dockerfile"
            assert actual == expected

    def test_resolve_dockerfile_relative_path__when_dockerfile_missing(self, tmp_path):
        project_dir = tmp_path / "infra" / "infra"
        with (
            env(MCP_WORKLOAD_DOCKERFILE_PATH=None),
        ):
            actual = FileBundler.resolve_dockerfile_relative_path(project_dir)

            expected = None
            assert actual == expected

    def test_resolve_dockerfile_relative_path__returns_default_dockerfile(
        self, tmp_path
    ):
        mcp_dir = tmp_path / "infra" / "mcp_server"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "Dockerfile").write_text("FROM scratch\n")
        with (
            env(MCP_WORKLOAD_DOCKERFILE_PATH=None),
        ):
            actual = FileBundler.resolve_dockerfile_relative_path(mcp_dir)

            expected = "Dockerfile"
            assert actual == expected
