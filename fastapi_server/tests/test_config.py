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

import os
from unittest.mock import patch

import pytest

from app import Config
from app.auth.oauth import OAuthImpl


def test__config__load_env_vars() -> None:
    # mix of prefixed and unprefixed env vars
    env_vars = dict(
        # The format of secrets in the DataRobot Custom App env
        MLOPS_RUNTIME_PARAM_SESSION_SECRET_KEY='{"type":"credential","payload":{"credentialType":"api_token","apiToken":"test-secret-key"}}',
        MLOPS_RUNTIME_PARAM_DATAROBOT_OAUTH_PROVIDERS='["abc", "123"]',
        DATAROBOT_ENDPOINT="https://api.test.datarobot.com",
        DATAROBOT_API_TOKEN="local-test-datarobot-api-key",
    )

    with patch.dict(os.environ, env_vars, clear=True):
        config = Config()

        assert config.session_secret_key == "test-secret-key"
        assert config.datarobot_oauth_providers
        assert len(config.datarobot_oauth_providers) == 2
        assert config.datarobot_endpoint == "https://api.test.datarobot.com"
        assert config.datarobot_api_token == "local-test-datarobot-api-key"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.test.datarobot.com/api/v2",
        "https://api.test.datarobot.com/api/v2/",
        "https://api.test.datarobot.com/",
        "https://api.test.datarobot.com",
    ],
)
def test__config__application_endpoint(endpoint: str) -> None:
    base_env = dict(
        MLOPS_RUNTIME_PARAM_SESSION_SECRET_KEY='{"type":"credential","payload":{"credentialType":"api_token","apiToken":"test-key"}}',
        DATAROBOT_ENDPOINT=endpoint,
        DATAROBOT_API_TOKEN="test-token",
    )

    # Without application_id - uses localhost with default port
    with patch.dict(os.environ, base_env, clear=True):
        config = Config()
        assert config.application_id is None
        assert config.application_endpoint == "http://localhost:8080/api/v1"

    # Without application_id - uses localhost with custom PORT
    with patch.dict(os.environ, {**base_env, "PORT": "9000"}, clear=True):
        config = Config()
        assert config.application_endpoint == "http://localhost:9000/api/v1"

    # With application_id - uses datarobot_endpoint
    with patch.dict(
        os.environ,
        {**base_env, "APPLICATION_ID": "6978ed7637491dea39936243"},
        clear=True,
    ):
        config = Config()
        assert config.application_id == "6978ed7637491dea39936243"
        assert (
            config.application_endpoint
            == "https://api.test.datarobot.com/custom_applications/6978ed7637491dea39936243/api/v1"
        )


@pytest.mark.parametrize(
    "oauth_impl,expected_impl",
    [
        ("authlib", OAuthImpl.AUTHLIB),
        ("datarobot", OAuthImpl.DATAROBOT),
    ],
)
def test__config__oauth_impl(oauth_impl: str, expected_impl: OAuthImpl) -> None:
    base_env = dict(
        MLOPS_RUNTIME_PARAM_SESSION_SECRET_KEY='{"type":"credential","payload":{"credentialType":"api_token","apiToken":"test-key"}}',
        DATAROBOT_ENDPOINT="https://api.test.datarobot.com",
        DATAROBOT_API_TOKEN="test-token",
        OAUTH_IMPL=oauth_impl,
    )

    with patch.dict(os.environ, base_env, clear=True):
        assert Config().oauth_impl == expected_impl


@pytest.mark.parametrize(
    "oauth_provider,expected_impl",
    [
        ("authlib_provider.py", OAuthImpl.AUTHLIB),
        ("datarobot_provider.py", OAuthImpl.DATAROBOT),
        ("", OAuthImpl.DATAROBOT),  # default to datarobot
    ],
)
def test__config__oauth_provider_fallback(
    oauth_provider: str, expected_impl: OAuthImpl
) -> None:
    base_env = dict(
        MLOPS_RUNTIME_PARAM_SESSION_SECRET_KEY='{"type":"credential","payload":{"credentialType":"api_token","apiToken":"test-key"}}',
        DATAROBOT_ENDPOINT="https://api.test.datarobot.com",
        DATAROBOT_API_TOKEN="test-token",
        INFRA_ENABLE_OAUTH=oauth_provider,
    )

    with patch.dict(os.environ, base_env, clear=True):
        assert Config().oauth_impl == expected_impl


def test__config__allows_use_memory_space_before_memory_space_id_is_wired() -> None:
    config = Config(
        session_secret_key="test-secret",
        datarobot_endpoint="https://api.test.datarobot.com",
        datarobot_api_token="test-token",
        USE_MEMORY_SPACE=True,
        MEMORY_SPACE_ID=None,
    )
    assert config.use_memory_space is True
    assert config.memory_space_id is None
