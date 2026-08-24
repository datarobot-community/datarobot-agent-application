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

from datarobot_genai.core.config import register_config_provider

from agent.config import Config

# Hand agent/config.py to datarobot-genai as the authoritative config for this agent
# component: from here on the library resolves the DataRobot connection and every LLM
# through Config instead of reading the environment on its own. Importing this package
# is what puts it in place, and NAT imports it during plugin discovery, before it builds
# the workflow.
register_config_provider(Config, default_llm_name="llm")

# Imported after the call above, because agent code may build an LLM at import time.
from agent.myagent import MyAgent  # noqa: E402

__all__ = ["MyAgent", "Config"]
