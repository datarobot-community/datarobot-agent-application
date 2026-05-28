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

"""Normalize memory-service session metadata keys for reads."""

from __future__ import annotations

import re
from typing import Any

from datarobot.models.memory import Session

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])([A-Z])")


def camel_to_snake(name: str) -> str:
    """Convert a camelCase or PascalCase key to snake_case."""
    if "_" in name:
        return name
    return _CAMEL_BOUNDARY.sub(r"_\1", name).lower()


def normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    Return metadata with snake_case keys.

    The memory-service REST API may return camelCase metadata; application code
    writes snake_case. Prefer an existing snake_case value when both forms appear.
    """
    if not metadata:
        return {}
    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        snake = camel_to_snake(key)
        if snake in normalized:
            if "_" in key:
                normalized[snake] = value
            continue
        normalized[snake] = value
    return normalized


def session_metadata(session: Session) -> dict[str, Any]:
    """Normalized metadata for a memory-service session."""
    return normalize_metadata(session.metadata)
