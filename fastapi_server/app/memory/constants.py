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

"""Shared limits and helpers for memory-space API usage."""

import hashlib
from urllib.parse import quote
from uuid import UUID

MEMORY_SPACE_MAX_RETRIEVAL_LIMIT = 100

# Session metadata ``v`` discriminates document types in a shared Memory Space (not
# per-type schema revisions). Chat sessions are unversioned; identity and user
# registries filter scans on these values so lookups do not cross types.
IDENTITY_METADATA_VERSION = 1
USER_METADATA_VERSION = 2


def chat_session_description(chat_uuid: UUID) -> str:
    """Indexed session description keyed by the app's chat UUID."""
    return f"/chat/{chat_uuid}"


def thread_session_description(thread_id: str) -> str:
    """Indexed session description keyed by the AG-UI thread id."""
    return f"/thread/{thread_id}"


def _encode_description_segment(value: str) -> str:
    return quote(value, safe="")


def identity_by_user_provider_description(user_id: int, provider_type: str) -> str:
    """Indexed session description for identity create and get_by_user_id lookups."""
    return f"/user/{user_id}/identity/{_encode_description_segment(provider_type)}"


def user_by_email_description(email: str) -> str:
    """Indexed session description for user create and get_user(email=...) lookups."""
    return f"/user/email/{_encode_description_segment(email)}"


# Stable 24-hex id (BSON ObjectId length) for the app agent: memory sessions include this
# as a participant, and assistant/tool/system events use it as emitter id.
MEMORY_APP_AGENT_PARTICIPANT_ID = hashlib.sha256(
    b"datarobot-agent-app:memory-service-app-agent"
).hexdigest()[:24]
