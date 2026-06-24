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

from typing import Optional

from datarobot.core.config import DataRobotAppFrameworkBaseSettings


class UserAppConfig(DataRobotAppFrameworkBaseSettings):
    """User-specific application configuration.

    Extends DataRobotAppFrameworkBaseSettings which provides automatic support for:
    - Environment variables (including MLOPS_RUNTIME_PARAM_* extraction)
    - .env file
    - pulumi_config.json (lowest priority)
    """

    user_name: str = "default-user"


# Global configuration instance
_user_config: Optional[UserAppConfig] = None


def get_user_config() -> UserAppConfig:
    """Get the global user configuration instance."""
    global _user_config
    if _user_config is None:
        _user_config = UserAppConfig()
    return _user_config
