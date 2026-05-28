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

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Final, Iterator

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

DATAROBOT_USER_ID_HEADER: Final[str] = "X-DataRobot-User-Id"

_MEMORY_PARTICIPANT_ID_LEN = 24

_memory_participant_id: ContextVar[str | None] = ContextVar(
    "memory_participant_id", default=None
)


def normalize_memory_participant_id(raw: str | None) -> str | None:
    """Normalize ``X-DataRobot-User-Id`` (or similar) to a 24-char lowercase hex id."""
    if not raw:
        return None
    candidate = raw.strip().lower()
    if len(candidate) != _MEMORY_PARTICIPANT_ID_LEN:
        return None
    try:
        int(candidate, 16)
    except ValueError:
        return None
    return candidate


def get_memory_participant_id_from_request(request: Request) -> str | None:
    """Return a validated memory-service participant id from the DataRobot user header."""
    return normalize_memory_participant_id(
        request.headers.get(DATAROBOT_USER_ID_HEADER)
    )


def get_memory_participant_id() -> str | None:
    """Return the memory participant id bound for the current request/task."""
    return _memory_participant_id.get()


@contextmanager
def memory_participant_id_context(
    memory_participant_id: str | None,
) -> Iterator[None]:
    """Bind a memory participant id for the duration of a block (tests, scripts)."""
    token = _memory_participant_id.set(memory_participant_id)
    try:
        yield
    finally:
        _memory_participant_id.reset(token)


def bind_memory_participant_id(memory_participant_id: str | None) -> Token[str | None]:
    """Bind a memory participant id; caller must reset the returned token."""
    return _memory_participant_id.set(memory_participant_id)


def reset_memory_participant_id(token: Token[str | None]) -> None:
    _memory_participant_id.reset(token)


class MemoryParticipantMiddleware:
    """Bind ``X-DataRobot-User-Id`` to request-scoped memory participant context."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        token = bind_memory_participant_id(
            get_memory_participant_id_from_request(request)
        )
        try:
            await self.app(scope, receive, send)
        finally:
            reset_memory_participant_id(token)
