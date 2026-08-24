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
"""Tests that agent/config.py is the configuration the agent actually runs on.

These guard the contract behind `agent/__init__.py`: `datarobot-genai` must resolve
this agent's `Config`, and every LLM setting it uses must come off that class. If these
fail, the library has fallen back to reading the environment on its own and the values
in `agent/config.py` are being ignored.
"""

from datarobot_genai.core.config import Config as GenAIConfig
from datarobot_genai.core.config import (
    LLMType,
    default_assume_native_tool_calling_when_unmapped,
    get_max_history_messages_default,
    registered_default_llm_name,
    resolve_config,
)

from agent import Config


def test_genai_resolves_the_agent_config() -> None:
    """The library must hand back this agent's Config, not its own."""
    resolved = resolve_config()

    assert isinstance(resolved, Config)
    # This agent's Config stands on its own. Inheriting the library's config class would
    # hand ownership of the fields back to the library.
    assert not isinstance(resolved, GenAIConfig)


def test_genai_resolves_the_agent_llm_instance_name() -> None:
    """A call site with no LLM name of its own must target this agent's LLM."""
    assert registered_default_llm_name() == "llm"


def test_llm_config_is_built_from_agent_config_fields() -> None:
    """The resolved LLM config must be built from the agent's own fields."""
    config = Config(
        datarobot_endpoint="https://example.datarobot.com/api/v2",
        datarobot_api_token="token",
        llm_deployment_id="deployment-id",
        llm_default_model="datarobot/azure/gpt-5-mini-2025-08-07",
        llm_use_datarobot_llm_gateway=False,
    )

    llm_config = config.resolve_llm_config(name="llm")

    assert llm_config.datarobot_endpoint == "https://example.datarobot.com/api/v2"
    assert llm_config.datarobot_api_token == "token"
    assert llm_config.llm_deployment_id == "deployment-id"
    assert llm_config.llm_default_model == "datarobot/azure/gpt-5-mini-2025-08-07"
    assert llm_config.get_llm_type() == LLMType.DEPLOYMENT


def test_library_reads_the_agent_config_runtime_defaults() -> None:
    """What the library resolves must equal what agent/config.py declares.

    These two settings are still read off the library's own config class rather than
    through the registered provider, so they line up only while the declared defaults
    match. A failure here after changing a default above means the library is not
    reading that field yet and the change has no effect at runtime.
    """
    config = Config()

    assert get_max_history_messages_default() == config.max_history_messages
    assert (
        default_assume_native_tool_calling_when_unmapped()
        == config.assume_native_tool_calling_when_unmapped
    )
