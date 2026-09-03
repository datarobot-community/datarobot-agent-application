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

from mcp_server_clients.workload_artifact_pulumi import (
    WorkloadGeneratedImageArtifactProvider,
    WorkloadImageArtifactProvider,
    _delete_artifact,
    _diff_changed,
)


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


def _provided_inputs() -> dict:
    return {
        "workload_api_endpoint": "https://api.example.com",
        "artifact_name": "mcp-server",
        "catalog_id": "cat",
        "catalog_version_id": "ver",
        "dockerfile_relative_path": "Dockerfile",
        "container_name": "mcp-server",
        "container_port": 8080,
        "environment_vars": [{"name": "FOO", "value": "bar"}],
        "routes": [{"path": "/mcp", "auth": "required"}],
        "build_timeout_s": 6000,
        "source_hash": "hash",
    }


def _generated_inputs() -> dict:
    return {
        "workload_api_endpoint": "https://api.example.com",
        "artifact_name": "mcp-server",
        "catalog_id": "cat",
        "catalog_version_id": "ver",
        "execution_environment_id": "ee",
        "execution_environment_version_id": "ee-ver",
        "entrypoint": ["python", "-m", "app.main"],
        "container_name": "mcp-server",
        "container_port": 8080,
        "environment_vars": [],
        "routes": None,
        "build_timeout_s": 6000,
        "source_hash": "hash",
    }


class TestDiffChanged:
    def test_diff_changed_detects_tracked_key_change(self) -> None:
        actual = _diff_changed(
            {"container_port": 8080}, {"container_port": 9000}, ("container_port",)
        ).changes
        expected = True
        assert actual == expected

    def test_diff_changed_no_changes_when_tracked_keys_match(self) -> None:
        actual = _diff_changed(
            {"source_hash": "same"}, {"source_hash": "same"}, ("source_hash",)
        ).changes
        expected = False
        assert actual == expected


class TestDeleteArtifact:
    def test_delete_artifact_calls_workload_client_delete(self) -> None:
        mock_client = MagicMock()
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                "mcp_server_clients.workload_artifact_pulumi.WorkloadClient",
                return_value=mock_client,
            ),
        ):
            _delete_artifact("https://api.example.com", "art-1")
        actual = mock_client.delete_artifact.call_args.args[0]
        expected = "art-1"
        assert actual == expected


class TestWorkloadImageArtifactProvider:
    def test_create_returns_artifact_id(self) -> None:
        provider = WorkloadImageArtifactProvider()
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                "mcp_server_clients.workload_artifact_pulumi.build_artifact_with_provided_dockerfile",
                return_value="art-1",
            ),
        ):
            result = provider.create(_provided_inputs())
        actual = result.id
        expected = "art-1"
        assert actual == expected

    def test_diff_replaces_when_dockerfile_path_changes(self) -> None:
        provider = WorkloadImageArtifactProvider()
        actual = provider.diff(
            "art-1",
            {"dockerfile_relative_path": "Dockerfile"},
            {"dockerfile_relative_path": "docker/Other"},
        ).changes
        expected = True
        assert actual == expected

    def test_delete_removes_artifact(self) -> None:
        provider = WorkloadImageArtifactProvider()
        mock_client = MagicMock()
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                "mcp_server_clients.workload_artifact_pulumi.WorkloadClient",
                return_value=mock_client,
            ),
        ):
            provider.delete(
                "art-1", {"workload_api_endpoint": "https://api.example.com"}
            )
        actual = mock_client.delete_artifact.call_args.args[0]
        expected = "art-1"
        assert actual == expected


class TestWorkloadGeneratedImageArtifactProvider:
    def test_create_returns_artifact_id(self) -> None:
        provider = WorkloadGeneratedImageArtifactProvider()
        with (
            env(DATAROBOT_API_TOKEN="token"),
            patch(
                "mcp_server_clients.workload_artifact_pulumi.build_artifact_with_generated_dockerfile",
                return_value="art-gen",
            ),
        ):
            result = provider.create(_generated_inputs())
        actual = result.id
        expected = "art-gen"
        assert actual == expected

    def test_diff_replaces_when_entrypoint_changes(self) -> None:
        provider = WorkloadGeneratedImageArtifactProvider()
        actual = provider.diff(
            "art-1",
            {"entrypoint": ["python", "-m", "app.main"]},
            {"entrypoint": ["python", "server.py"]},
        ).changes
        expected = True
        assert actual == expected
