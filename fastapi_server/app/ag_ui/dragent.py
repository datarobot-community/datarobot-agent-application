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
import logging
from typing import Any, AsyncGenerator, Dict, List

import httpx
import httpx_sse
from ag_ui.core import (
    BaseEvent,
    Event,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
)
from pydantic import BaseModel

from app.ag_ui.base import AGUIAgent
from app.ag_ui.dr import _heartbeat_generator, _merge_async_generators
from app.config import Config

_DEFAULT_STREAM_TIMEOUT_SECONDS = 600

logger = logging.getLogger(__name__)


def _strip_none(d: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with None values so ag_ui models with extra='forbid' don't reject them."""
    return {k: v for k, v in d.items() if v is not None}


class DRAgentEventResponse(BaseModel):
    events: List[Event] = []


class DRAgentAGUIAgent(AGUIAgent):
    """AG-UI agent that uses the DRAgent server's /generate/stream endpoint."""

    def __init__(
        self,
        name: str,
        config: Config,
        headers: Dict[str, str] | None = None,
        heartbeat_interval: float = 15.0,
        check_interval: float = 1.0,
    ) -> None:
        super().__init__(name)
        self.url = f"{config.agent_endpoint}/generate/stream"

        self.agent_headers: Dict[str, str] = {
            "Authorization": f"Bearer {config.datarobot_api_token}",
            "Content-Type": "application/json",
        }
        if headers:
            self.agent_headers.update(headers)

        self.heartbeat_interval = heartbeat_interval
        self.check_interval = check_interval

    async def run(self, input: RunAgentInput) -> AsyncGenerator[BaseEvent, None]:
        main_finished_ref = [False]
        heartbeat_gen = _heartbeat_generator(
            input.thread_id,
            input.run_id,
            main_finished_ref,
            self.heartbeat_interval,
            self.check_interval,
        )
        async for event in _merge_async_generators(
            self._handle_stream_events(input), heartbeat_gen, main_finished_ref
        ):
            yield event

    async def _handle_stream_events(
        self, input: RunAgentInput
    ) -> AsyncGenerator[BaseEvent, None]:
        yield RunStartedEvent(thread_id=input.thread_id, run_id=input.run_id)
        try:
            body = input.model_dump_json(by_alias=True)

            logger.info("Sending request to DRAgent server's /generate/stream endpoint")

            events_yielded = False
            async with httpx.AsyncClient(
                timeout=_DEFAULT_STREAM_TIMEOUT_SECONDS
            ) as client:
                async with httpx_sse.aconnect_sse(
                    client,
                    "POST",
                    self.url,
                    headers=self.agent_headers,
                    content=body,
                ) as event_source:
                    if event_source.response.status_code >= 400:
                        error_body = await event_source.response.aread()
                        yield RunErrorEvent(
                            message=f"DRAgent server returned error {event_source.response.status_code}: {error_body.decode()}",
                            thread_id=input.thread_id,
                            run_id=input.run_id,
                        )
                        return
                    async for sse in event_source.aiter_sse():
                        if not sse.data:
                            continue
                        raw = json.loads(sse.data)
                        raw["events"] = [
                            _strip_none(e) for e in raw.get("events", []) or []
                        ]
                        response = DRAgentEventResponse.model_validate(raw)
                        for event in response.events:
                            # Filter out RunStartedEvent/RunFinishedEvent from the DRAgent server
                            # since they have empty run_id/thread_id, and we emit our own.
                            if isinstance(event, (RunStartedEvent, RunFinishedEvent)):
                                continue
                            logger.debug("Yielding event: %s", event.type)
                            events_yielded = True
                            yield event
                            if isinstance(event, RunErrorEvent):
                                # The run already ended in error; no further event
                                # (including our own RunFinishedEvent below) may
                                # follow for this run.
                                return

            logger.info("Stream has finished")

            if not events_yielded:
                raise RuntimeError(
                    "No events received from the DRAgent server. Please check if the server is running."
                )

            yield RunFinishedEvent(thread_id=input.thread_id, run_id=input.run_id)

        except Exception as e:
            logger.exception("Error during DRAgent agent run")
            yield RunErrorEvent(
                message=str(e), thread_id=input.thread_id, run_id=input.run_id
            )
