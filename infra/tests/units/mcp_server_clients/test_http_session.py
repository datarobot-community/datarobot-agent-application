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

from mcp_server_clients.http_session import (
    RETRY_STATUS_FORCELIST,
    TOTAL_RETRIES,
    create_datarobot_api_session,
)


def test_session_sets_bearer_auth():
    session = create_datarobot_api_session("secret-token")

    assert session.headers["Authorization"] == "Bearer secret-token"


def test_session_merges_default_headers():
    session = create_datarobot_api_session(
        "token", default_headers={"Content-Type": "application/json"}
    )

    assert session.headers["Authorization"] == "Bearer token"
    assert session.headers["Content-Type"] == "application/json"


def test_retries_are_mounted_for_both_schemes():
    session = create_datarobot_api_session("token")

    for prefix in ("https://", "http://"):
        retry = session.get_adapter(prefix).max_retries
        assert retry.total == TOTAL_RETRIES
        assert retry.status_forcelist == RETRY_STATUS_FORCELIST


def test_post_is_not_retried_so_creates_are_not_duplicated():
    """Files/Workload APIs create resources with POST; a retry could duplicate them."""
    retry = create_datarobot_api_session("token").get_adapter("https://").max_retries

    assert "POST" not in retry.allowed_methods
    assert {"GET", "PUT", "DELETE"} <= set(retry.allowed_methods)


def test_status_errors_are_returned_not_raised_as_retry_error():
    """Callers surface the response body themselves, so keep the final response."""
    retry = create_datarobot_api_session("token").get_adapter("https://").max_retries

    assert retry.raise_on_status is False
