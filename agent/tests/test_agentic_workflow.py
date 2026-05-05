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
import json
import os
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest
from ag_ui.core import (
    EventType,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageChunkEvent,
    UserMessage,
)


class TestCustomModel:
    def test_load_model(self):
        from custom import load_model

        (thread_pool_executor, event_loop) = load_model("")
        assert isinstance(thread_pool_executor, ThreadPoolExecutor)
        assert isinstance(event_loop, type(asyncio.get_event_loop()))
        thread_pool_executor.shutdown()

    @patch("agent.myagent.get_llm")
    @patch("agent.myagent.MyAgent")
    @patch.dict(
        os.environ,
        {"LLM_DEPLOYMENT_ID": "TEST_VALUE", "MEM0_API_KEY": "some_key"},
        clear=True,
    )
    @pytest.mark.parametrize("stream", [False, True])
    def test_chat(
        self,
        mock_agent,
        mock_get_llm,
        mock_agent_response,
        stream,
        load_model_result,
    ):
        from custom import chat

        # Setup mocks
        mock_agent_instance = MagicMock()
        mock_agent_instance.invoke = Mock(return_value=mock_agent_response)
        mock_agent.return_value = mock_agent_instance
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        completion_create_params = {
            "model": "test-model",
            "messages": [{"role": "user", "content": '{"topic": "test"}'}],
            "environment_var": True,
            "stream": stream,
        }
        kwargs = {
            "headers": {
                "x-datarobot-api-key": "secret-key",
                "x-datarobot-api-token": "secret-token",
            }
        }

        response = chat(
            copy(completion_create_params),
            load_model_result=load_model_result,
            **kwargs,
        )

        if stream:
            actual_list = [json.loads(chunk.model_dump_json()) for chunk in response]
            expected_list = [
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "agent result",
                                "function_call": None,
                                "refusal": None,
                                "role": "assistant",
                                "tool_calls": None,
                            },
                            "finish_reason": None,
                            "index": 0,
                            "logprobs": None,
                        },
                    ],
                    "created": ANY,
                    "event": ANY,
                    "id": ANY,
                    "model": "test-model",
                    "object": "chat.completion.chunk",
                    "pipeline_interactions": None,
                    "service_tier": None,
                    "system_fingerprint": None,
                    "usage": {
                        "completion_tokens": 1,
                        "completion_tokens_details": None,
                        "prompt_tokens": 2,
                        "prompt_tokens_details": None,
                        "total_tokens": 3,
                    },
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "",
                                "function_call": None,
                                "refusal": None,
                                "role": "assistant",
                                "tool_calls": None,
                            },
                            "finish_reason": None,
                            "index": 0,
                            "logprobs": None,
                        },
                    ],
                    "created": ANY,
                    "event": ANY,
                    "id": ANY,
                    "model": "test-model",
                    "object": "chat.completion.chunk",
                    "pipeline_interactions": None,
                    "service_tier": None,
                    "system_fingerprint": None,
                    "usage": {
                        "completion_tokens": 1,
                        "completion_tokens_details": None,
                        "prompt_tokens": 2,
                        "prompt_tokens_details": None,
                        "total_tokens": 3,
                    },
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "content": None,
                                "function_call": None,
                                "refusal": None,
                                "role": "assistant",
                                "tool_calls": None,
                            },
                            "finish_reason": "stop",
                            "index": 0,
                            "logprobs": None,
                        },
                    ],
                    "created": ANY,
                    "event": None,
                    "id": ANY,
                    "model": "test-model",
                    "object": "chat.completion.chunk",
                    "pipeline_interactions": ANY,
                    "service_tier": None,
                    "system_fingerprint": None,
                    "usage": {
                        "completion_tokens": 1,
                        "completion_tokens_details": None,
                        "prompt_tokens": 2,
                        "prompt_tokens_details": None,
                        "total_tokens": 3,
                    },
                },
            ]
            assert actual_list == expected_list
        else:
            actual = json.loads(response.model_dump_json())
            # Assert results
            expected = {
                "id": ANY,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "logprobs": None,
                        "message": {
                            "content": "agent result",
                            "refusal": None,
                            "role": "assistant",
                            "annotations": None,
                            "audio": None,
                            "function_call": None,
                            "tool_calls": None,
                        },
                    }
                ],
                "created": ANY,
                "model": "test-model",
                "object": "chat.completion",
                "service_tier": None,
                "system_fingerprint": None,
                "usage": {
                    "completion_tokens": 1,
                    "prompt_tokens": 2,
                    "total_tokens": 3,
                    "completion_tokens_details": None,
                    "prompt_tokens_details": None,
                },
                "pipeline_interactions": ANY,
            }
            assert actual == expected

        # Verify mocks were called correctly
        mock_get_llm.assert_called_once_with(model_name="test-model")
        mock_agent.assert_called_once_with(
            llm=mock_llm,
            forwarded_headers=kwargs["headers"],
            verbose=True,
            timeout=90,
        )

        assert mock_agent_instance.invoke.called
        assert mock_agent_instance.invoke.call_args[0][0].messages == [
            UserMessage(
                id="message_0",
                role="user",
                content='{"topic": "test"}',
                name=None,
                encrypted_value=None,
            ),
        ]

    @patch("agent.myagent.get_llm")
    @patch("agent.myagent.MyAgent")
    @patch.dict(os.environ, {"LLM_DEPLOYMENT_ID": "TEST_VALUE"}, clear=True)
    def test_chat_streaming(
        self,
        mock_agent,
        mock_get_llm,
        load_model_result,
    ):
        from custom import chat

        # Create a generator that yields AG-UI event streaming responses
        async def mock_streaming_generator():
            yield (
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id="t",
                    run_id="r",
                ),
                None,
                {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            )
            yield (
                TextMessageChunkEvent(
                    type=EventType.TEXT_MESSAGE_CHUNK,
                    message_id="m1",
                    delta="chunk1",
                ),
                None,
                {"completion_tokens": 1, "prompt_tokens": 2, "total_tokens": 3},
            )
            yield (
                TextMessageChunkEvent(
                    type=EventType.TEXT_MESSAGE_CHUNK,
                    message_id="m1",
                    delta="chunk2",
                ),
                None,
                {"completion_tokens": 2, "prompt_tokens": 2, "total_tokens": 4},
            )
            yield (
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id="t",
                    run_id="r",
                ),
                Mock(model_dump_json=MagicMock(return_value="interactions")),
                {"completion_tokens": 3, "prompt_tokens": 2, "total_tokens": 5},
            )

        # Setup mocks
        mock_agent_instance = MagicMock()
        mock_agent_instance.invoke = Mock(return_value=mock_streaming_generator())
        mock_agent.return_value = mock_agent_instance
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        completion_create_params = {
            "model": "test-model",
            "messages": [{"role": "user", "content": '{"topic": "test"}'}],
            "stream": True,
            "environment_var": True,
        }
        kwargs = {
            "headers": {
                "x-datarobot-api-key": "secret-key",
                "x-datarobot-api-token": "secret-token",
            }
        }

        response = chat(
            copy(completion_create_params),
            load_model_result=load_model_result,
            **kwargs,
        )

        # Verify response is an iterator
        assert hasattr(response, "__iter__")
        assert hasattr(response, "__next__")

        # Collect all chunks
        chunks = list(response)

        # Should have 4 chunks (2 with content + 1 RUN_FINISHED carrier + 1 final)
        assert len(chunks) == 4

        # First chunk with content
        chunk1 = json.loads(chunks[0].model_dump_json())
        assert chunk1["object"] == "chat.completion.chunk"
        assert chunk1["choices"][0]["delta"]["content"] == "chunk1"
        assert chunk1["choices"][0]["finish_reason"] is None
        assert chunk1["model"] == "test-model"

        # Second chunk with content
        chunk2 = json.loads(chunks[1].model_dump_json())
        assert chunk2["choices"][0]["delta"]["content"] == "chunk2"
        assert chunk2["choices"][0]["finish_reason"] is None

        # RUN_FINISHED carrier chunk (no content, AG-UI event attached)
        run_finished_chunk = json.loads(chunks[2].model_dump_json())
        assert run_finished_chunk["choices"][0]["delta"]["content"] == ""
        assert run_finished_chunk["choices"][0]["finish_reason"] is None
        assert run_finished_chunk["event"]["type"] == "RUN_FINISHED"

        # Final chunk
        final_chunk = json.loads(chunks[3].model_dump_json())
        assert final_chunk["choices"][0]["delta"]["content"] is None
        assert final_chunk["choices"][0]["finish_reason"] == "stop"
        assert final_chunk["pipeline_interactions"] == "interactions"
        assert final_chunk["usage"]["total_tokens"] == 5

        # Verify mocks were called correctly
        mock_get_llm.assert_called_once_with(model_name="test-model")
        mock_agent.assert_called_once_with(
            llm=mock_llm,
            forwarded_headers=kwargs["headers"],
            verbose=True,
            timeout=90,
        )
        assert mock_agent_instance.invoke.called
        assert mock_agent_instance.invoke.call_args[0][0].messages == [
            UserMessage(
                id="message_0",
                role="user",
                content='{"topic": "test"}',
                name=None,
                encrypted_value=None,
            ),
        ]
