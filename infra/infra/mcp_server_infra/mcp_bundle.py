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

"""Source bundle helpers for workload image builds."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pulumi

DOCKERFILE_RELATIVE_PATH = "Dockerfile"
PYPROJECT_RELATIVE_PATH = "pyproject.toml"
UV_LOCK_RELATIVE_PATH = "uv.lock"
START_SERVER_RELATIVE_PATH = "start_server.sh"
DOCKER_BUILD_CONTEXT_FILES = (
    DOCKERFILE_RELATIVE_PATH,
    PYPROJECT_RELATIVE_PATH,
    UV_LOCK_RELATIVE_PATH,
    START_SERVER_RELATIVE_PATH,
)

CRLF = b"\r\n"
LF = b"\n"


def ensure_docker_build_context_files(deployments_path: Path) -> None:
    """Verify Docker build files exist at the app root.

    Custom execution-environment builds and workload DockerfileProvided builds
    both use the app root as context. Source files live here permanently —
    nothing is mirrored into a ``docker/`` subdirectory.
    """
    missing = [
        relative_path
        for relative_path in DOCKER_BUILD_CONTEXT_FILES
        if not (deployments_path / relative_path).is_file()
    ]
    if missing:
        message = f"Docker build requires {', '.join(missing)} under {deployments_path}"
        pulumi.error(message)
        raise RuntimeError(message)


def get_docker_bundle_files(
    deployments_path: Path,
    dockerfile_relative_path: str = DOCKERFILE_RELATIVE_PATH,
) -> list[tuple[str, str]]:
    """
    Files required for DockerfileProvided workload builds.

    ``dockerfile_relative_path`` is the catalog-relative path the artifact spec
    points the build at (``MCP_WORKLOAD_DOCKERFILE_PATH``). The same path locates
    the Dockerfile on disk and places it in the bundle, so a custom location is
    uploaded where the build looks for it.

    The Dockerfile installs uv and runs ``uv sync --frozen`` against
    ``pyproject.toml``/``uv.lock`` at the bundle root -- already included via
    ``get_deployments_app_files`` -- and expects ``start_server.sh`` at the
    bundle root.
    """
    dockerfile_path = deployments_path / dockerfile_relative_path

    for required_path, relative_path in (
        (dockerfile_path, dockerfile_relative_path),
        (deployments_path / PYPROJECT_RELATIVE_PATH, PYPROJECT_RELATIVE_PATH),
        (deployments_path / UV_LOCK_RELATIVE_PATH, UV_LOCK_RELATIVE_PATH),
        (deployments_path / START_SERVER_RELATIVE_PATH, START_SERVER_RELATIVE_PATH),
    ):
        if not required_path.is_file():
            message = (
                f"Workload DockerfileProvided build requires {relative_path} "
                f"under {deployments_path}"
            )
            pulumi.error(message)
            raise RuntimeError(message)

    return [(str(dockerfile_path), dockerfile_relative_path)]


def merge_source_files(
    *file_groups: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge bundle entries, keeping the last occurrence for duplicate relative paths."""
    merged: dict[str, str] = {}
    for group in file_groups:
        for abs_path, rel_path in group:
            merged[rel_path] = abs_path
    return [(abs_path, rel_path) for rel_path, abs_path in sorted(merged.items())]


def get_workload_source_files(
    *,
    deployments_path: Path,
    dockerfile_relative_path: str | None,
    get_core_app_files: Callable[[], list[tuple[str, str]]],
) -> list[tuple[str, str]]:
    """Collect the Files catalog bundle for workload provisioning."""
    core_files = get_core_app_files()
    if dockerfile_relative_path is None:
        return core_files
    docker_files = get_docker_bundle_files(deployments_path, dockerfile_relative_path)
    return merge_source_files(core_files, docker_files)


def normalize_shell_scripts(
    source_files: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Rewrite bundled ``*.sh`` files to LF line endings and return the bundle.

    These run under ``/bin/sh`` in a Linux container, where a trailing CR sticks
    to the last token of every line -- ``then<CR>`` stops being the ``then``
    keyword and the parser runs off the end of the file. Windows checkouts can
    leave CRLF on disk and the bundle is uploaded byte for byte, so normalize
    here, the last point we control. Idempotent, and rewriting in place keeps
    the paths Pulumi tracks stable.
    """
    for abs_path, rel_path in source_files:
        if not rel_path.endswith(".sh"):
            continue
        path = Path(abs_path)
        content = path.read_bytes()
        if CRLF not in content:
            continue
        path.write_bytes(content.replace(CRLF, LF))
        pulumi.info(f"Normalized CRLF line endings to LF in {rel_path}")
    return source_files
