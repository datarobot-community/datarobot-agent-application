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

import json
from unittest.mock import patch

import pytest
import requests

from mcp_server_clients.files_api_client import (
    DEFAULT_REQUEST_TIMEOUT_S,
    TRANSIENT_POST_ATTEMPTS,
    UPLOAD_TIMEOUT_S,
    FilesApiClient,
)


def _json_response(status_code: int, payload: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode()
    return response


class TestFilesApiClient:
    def test_url_strips_trailing_slash_from_endpoint(self) -> None:
        client = FilesApiClient("https://api.example.com/", "token")
        actual = client._url("/files/fromFile/")
        expected = "https://api.example.com/files/fromFile/"
        assert actual == expected

    def test_create_catalog_returns_catalog_id_field(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(200, {"catalogId": "cat-1"})
        with patch.object(client._session, "post", return_value=response) as post:
            actual = client.create_catalog()
        expected = "cat-1"
        assert actual == expected
        assert post.call_args.kwargs["timeout"] == DEFAULT_REQUEST_TIMEOUT_S

    def test_create_catalog_falls_back_to_id_field(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(200, {"id": "cat-legacy"})
        with patch.object(client._session, "post", return_value=response):
            actual = client.create_catalog()
        expected = "cat-legacy"
        assert actual == expected

    def test_create_stage_returns_stage_id_field(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(200, {"stageId": "stage-1"})
        with patch.object(client._session, "post", return_value=response):
            actual = client.create_stage("cat-1")
        expected = "stage-1"
        assert actual == expected

    def test_apply_stage_returns_catalog_version_id_field(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(200, {"catalogVersionId": "ver-1"})
        with patch.object(client._session, "post", return_value=response):
            actual = client.apply_stage("cat-1", "stage-1")
        expected = "ver-1"
        assert actual == expected

    def test_upload_to_stage_uses_upload_timeout(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(200, {})
        with patch.object(client._session, "post", return_value=response) as post:
            client.upload_to_stage("cat-1", "stage-1", "app.py", b"code")
        actual = post.call_args.kwargs["timeout"]
        expected = UPLOAD_TIMEOUT_S
        assert actual == expected

    def test_upload_to_stage_retries_transient_gateway_errors(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        responses = [
            _json_response(502, {"detail": "Bad Gateway"}),
            _json_response(503, {"detail": "Service Unavailable"}),
            _json_response(200, {}),
        ]
        with (
            patch.object(client._session, "post", side_effect=responses) as post,
            patch("mcp_server_clients.files_api_client.time.sleep") as sleep,
        ):
            client.upload_to_stage("cat-1", "stage-1", "app.py", b"code")
        assert post.call_count == 3
        assert sleep.call_count == 2

    def test_upload_to_stage_raises_after_exhausting_transient_retries(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(502, {"detail": "Bad Gateway"})
        response.reason = "Bad Gateway"
        with (
            patch.object(client._session, "post", return_value=response) as post,
            patch("mcp_server_clients.files_api_client.time.sleep"),
            pytest.raises(requests.HTTPError),
        ):
            client.upload_to_stage("cat-1", "stage-1", "app.py", b"code")
        assert post.call_count == TRANSIENT_POST_ATTEMPTS

    def test_apply_stage_does_not_retry_transient_errors(self) -> None:
        """Re-applying an already-applied stage fails, so apply must stay single-shot."""
        client = FilesApiClient("https://api.example.com", "token")
        response = _json_response(502, {"detail": "Bad Gateway"})
        response.reason = "Bad Gateway"
        with (
            patch.object(client._session, "post", return_value=response) as post,
            pytest.raises(requests.HTTPError),
        ):
            client.apply_stage("cat-1", "stage-1")
        assert post.call_count == 1

    def test_upload_bundle_returns_catalog_and_version_ids(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        with (
            patch.object(client, "create_catalog", return_value="cat"),
            patch.object(client, "create_stage", return_value="stage"),
            patch.object(client, "upload_to_stage"),
            patch.object(client, "apply_stage", return_value="ver"),
        ):
            actual = client.upload_bundle([("app.py", b"code")])
        expected = ("cat", "ver")
        assert actual == expected

    @pytest.mark.parametrize("status_code", [404, 409])
    def test_delete_catalog_tolerates_missing_or_referenced_catalog(
        self, status_code: int
    ) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = requests.Response()
        response.status_code = status_code
        with patch.object(client._session, "delete", return_value=response):
            client.delete_catalog("cat-1")

    def test_delete_catalog_raises_on_other_errors(self) -> None:
        client = FilesApiClient("https://api.example.com", "token")
        response = requests.Response()
        response.status_code = 500
        response.reason = "Internal Server Error"
        response._content = b'{"detail":"boom"}'
        response.url = "https://api.example.com/files/cat-1/"
        response.request = requests.Request(method="DELETE", url=response.url).prepare()
        with (
            patch.object(client._session, "delete", return_value=response),
            pytest.raises(requests.HTTPError),
        ):
            client.delete_catalog("cat-1")
