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

import asyncio
import logging
from typing import AsyncGenerator

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
)

logger = logging.getLogger(__name__)


async def _merge_async_generators(
    main_gen: AsyncGenerator[BaseEvent, None],
    heartbeat_gen: AsyncGenerator[BaseEvent, None],
    main_finished_ref: list[bool],
) -> AsyncGenerator[BaseEvent, None]:
    """Merge main stream with heartbeat, stopping heartbeat when main stream finishes."""
    queue: asyncio.Queue[BaseEvent | None] = asyncio.Queue()

    async def _run_main() -> None:
        try:
            async for event in main_gen:
                await queue.put(event)
        except Exception as e:
            logger.exception("Error in main generator", extra={"error": str(e)})
        finally:
            main_finished_ref[0] = True
            await queue.put(None)  # Signal main stream finished

    async def _run_heartbeat() -> None:
        try:
            async for event in heartbeat_gen:
                await queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("Error in heartbeat generator", extra={"error": str(e)})

    # Start both generators
    main_task = asyncio.create_task(_run_main())
    heartbeat_task = asyncio.create_task(_run_heartbeat())

    try:
        while True:
            event = await queue.get()
            if event is None:
                # Main stream finished, cancel heartbeat and wait for it
                if not heartbeat_task.done():
                    heartbeat_task.cancel()
                break
            yield event
    finally:
        # Cancel heartbeat if still running
        if not heartbeat_task.done():
            heartbeat_task.cancel()
        # Wait for both tasks to finish
        await asyncio.gather(main_task, heartbeat_task, return_exceptions=True)


async def _heartbeat_generator(
    thread_id: str,
    run_id: str,
    main_finished_ref: list[bool],
    heartbeat_interval: float,
    check_interval: float,
) -> AsyncGenerator[BaseEvent, None]:
    """Generate heartbeat events every 15 seconds until main stream finishes."""

    while True:
        # Sleep in smaller intervals to check if main stream finished
        elapsed = 0.0
        while elapsed < heartbeat_interval:
            if main_finished_ref[0]:
                return
            await asyncio.sleep(min(check_interval, heartbeat_interval - elapsed))
            elapsed += check_interval

        if main_finished_ref[0]:
            return

        # Create a heartbeat event using Event with CUSTOM type
        heartbeat_event = CustomEvent(
            name="Heartbeat",
            value={"thread_id": thread_id, "run_id": run_id},
        )
        yield heartbeat_event
