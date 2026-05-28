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

import asyncio

import pytest

from app.memory.locks import memory_space_lock


@pytest.mark.asyncio
async def test_memory_space_lock_serializes_same_key() -> None:
    order: list[int] = []

    async def worker(n: int) -> None:
        async with memory_space_lock("test-key"):
            order.append(n)
            await asyncio.sleep(0.05)

    await asyncio.gather(worker(1), worker(2))
    assert order == [1, 2] or order == [2, 1]
    assert len(order) == 2
