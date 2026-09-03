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

import time
from typing import Any

import requests

from mcp_server_clients.http_session import (
    RETRY_STATUS_FORCELIST,
    create_datarobot_api_session,
)

DEFAULT_REQUEST_TIMEOUT_S = 60
UPLOAD_TIMEOUT_S = 600
TRANSIENT_POST_ATTEMPTS = 4
TRANSIENT_BACKOFF_BASE_S = 2.0
TRANSIENT_BACKOFF_MAX_S = 15.0


class FilesApiClient:
    def __init__(self, endpoint: str, token: str) -> None:
        self._base = endpoint.rstrip("/")
        self._token = token
        self._session = create_datarobot_api_session(token)

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    def _post_retrying_transient(self, url: str, **kwargs: Any) -> requests.Response:
        """POST with retries on gateway-transient statuses (429/5xx).

        The shared session deliberately excludes POST from its retry policy
        (see http_session.py) because create-POSTs can duplicate resources.
        This wrapper is only for the repeat-safe subset: catalog/stage creation
        and stage uploads, where re-sending the same payload at worst
        overwrites identical staged content or leaves an inert empty stage.
        ``apply_stage`` must NOT use it — re-applying an already-applied stage
        fails outright.
        """
        resp: requests.Response | None = None
        for attempt in range(1, TRANSIENT_POST_ATTEMPTS + 1):
            resp = self._session.post(url, **kwargs)
            if resp.status_code not in RETRY_STATUS_FORCELIST:
                return resp
            if attempt < TRANSIENT_POST_ATTEMPTS:
                delay = min(
                    TRANSIENT_BACKOFF_BASE_S * 2 ** (attempt - 1),
                    TRANSIENT_BACKOFF_MAX_S,
                )
                time.sleep(delay)
        assert resp is not None  # loop always runs at least once
        return resp

    def create_catalog(self) -> str:
        resp = self._post_retrying_transient(
            self._url("/files/fromFile/"),
            headers={"Authorization": f"Bearer {self._token}"},
            files={
                "file": (".placeholder", b"placeholder", "application/octet-stream")
            },
            timeout=DEFAULT_REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("catalogId") or data["id"]

    def create_stage(self, catalog_id: str) -> str:
        resp = self._post_retrying_transient(
            self._url(f"/files/{catalog_id}/stages/"),
            headers={"Content-Type": "application/json"},
            timeout=DEFAULT_REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("stageId") or data["id"]

    def upload_to_stage(
        self, catalog_id: str, stage_id: str, file_name: str, content: bytes
    ) -> None:
        resp = self._post_retrying_transient(
            self._url(f"/files/{catalog_id}/stages/{stage_id}/upload/"),
            headers={"Authorization": f"Bearer {self._token}"},
            files={"file": (file_name, content, "application/octet-stream")},
            timeout=UPLOAD_TIMEOUT_S,
        )
        resp.raise_for_status()

    def apply_stage(self, catalog_id: str, stage_id: str) -> str:
        resp = self._session.post(
            self._url(f"/files/{catalog_id}/fromStage/"),
            json={"stageId": stage_id, "overwrite": "replace"},
            timeout=DEFAULT_REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("catalogVersionId") or data["versionId"]

    def upload_bundle(self, files: list[tuple[str, bytes]]) -> tuple[str, str]:
        catalog_id = self.create_catalog()
        stage_id = self.create_stage(catalog_id)
        for name, content in files:
            self.upload_to_stage(catalog_id, stage_id, name, content)
        version_id = self.apply_stage(catalog_id, stage_id)
        return catalog_id, version_id

    def delete_catalog(self, catalog_id: str) -> None:
        resp = self._session.delete(
            self._url(f"/files/{catalog_id}/"), timeout=DEFAULT_REQUEST_TIMEOUT_S
        )
        # 404: already gone. 409: still referenced (e.g. by an artifact the
        # platform retains as workload revision history) — treat as released
        # rather than failing the update.
        if resp.status_code in (404, 409):
            return
        resp.raise_for_status()
