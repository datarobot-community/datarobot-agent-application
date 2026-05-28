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

import uuid as uuidpkg

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.memory.participant import (
    get_memory_participant_id,
    get_memory_participant_id_from_request,
    memory_participant_id_context,
)
from app.memory.repos import memory_space_participant_id


def test_get_memory_participant_id_from_request() -> None:
    dr_user_id = "507f1f77bcf86cd799439011"
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-datarobot-user-id", dr_user_id.upper().encode())],
        }
    )
    assert get_memory_participant_id_from_request(request) == dr_user_id

    invalid = Request(
        {
            "type": "http",
            "headers": [(b"x-datarobot-user-id", b"invalid")],
        }
    )
    assert get_memory_participant_id_from_request(invalid) is None


def test_memory_participant_id_context() -> None:
    dr_user_id = "507f1f77bcf86cd799439011"
    user_uuid = uuidpkg.UUID("12345678-1234-5678-1234-567812345678")

    assert get_memory_participant_id() is None
    with memory_participant_id_context(dr_user_id):
        assert get_memory_participant_id() == dr_user_id
        assert memory_space_participant_id(user_uuid) == dr_user_id
    assert get_memory_participant_id() is None


def test_memory_participant_middleware_binds_header() -> None:
    dr_user_id = "507f1f77bcf86cd799439011"
    app = FastAPI()

    @app.get("/probe")
    async def probe() -> dict[str, str | None]:
        return {"participant_id": get_memory_participant_id()}

    from app.memory import MemoryParticipantMiddleware

    app.add_middleware(MemoryParticipantMiddleware)

    client = TestClient(app)
    response = client.get("/probe", headers={"X-DataRobot-User-Id": dr_user_id.upper()})
    assert response.status_code == 200
    assert response.json()["participant_id"] == dr_user_id
