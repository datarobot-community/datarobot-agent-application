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

"""Shared authenticated HTTP session for the DataRobot Files and Workload APIs."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TOTAL_RETRIES = 3
BACKOFF_FACTOR = 0.5
RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)


def create_datarobot_api_session(
    token: str, default_headers: dict[str, str] | None = None
) -> requests.Session:
    """A DataRobot API session with bearer auth and retries on transient failures.

    Retries are limited to urllib3's default idempotent methods. POST is
    deliberately excluded: the Files and Workload APIs create resources with POST
    (catalogs, stages, artifacts, builds), so a retry after a request that
    actually succeeded server-side would create a duplicate. The repeat-safe
    POSTs (catalog/stage creation, stage uploads) layer their own transient
    retry on top — see FilesApiClient._post_retrying_transient.

    ``raise_on_status=False`` keeps the final response instead of raising
    ``requests.exceptions.RetryError``, so callers' own error handling can still
    surface the response body — the Workload API returns the actionable
    validation detail there.
    """
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    if default_headers:
        session.headers.update(default_headers)

    retry = Retry(
        total=TOTAL_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
