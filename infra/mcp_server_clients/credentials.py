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

"""API token sourcing for dynamic resource providers.

The token is deliberately read from the environment inside provider operations
instead of being passed as a resource property: dynamic resource inputs and
outputs are serialized into the Pulumi state file, and the token must never be
stored there in plaintext.
"""

import os

DATAROBOT_API_TOKEN_ENV = "DATAROBOT_API_TOKEN"


def datarobot_api_token() -> str:
    token = os.getenv(DATAROBOT_API_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(
            f"{DATAROBOT_API_TOKEN_ENV} must be set in the environment for workload "
            "provisioning (including `pulumi destroy`); it is intentionally not "
            "stored in Pulumi state."
        )
    return token
