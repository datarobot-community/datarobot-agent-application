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
import logging

from datarobot_pulumi_utils.common.feature_flags import fetch_flag_statuses

from datarobot.errors import ClientError


logger = logging.getLogger(__name__)


def is_lineage_feature_enabled() -> bool:
    try:
        flag_name = "ENABLE_MCP_TOOLS_GALLERY_SUPPORT"
        flag_status = fetch_flag_statuses([flag_name])
        return flag_status[flag_name]
    except ClientError:
        error_message = (
            "Feature flag retrieval error. Feature flag evaluation falls back to False."
        )
        logger.warning(error_message)
        return False
