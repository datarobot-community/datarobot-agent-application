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
import pytest

from infra.mcp_server_infra.mcp_oauth_configs import (
    AUTHORIZATION_SERVERS_ENV_VAR,
    ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR,
    OAUTH_METADATA_ENV_VARS,
    OAUTH_PROTECTED_RESOURCE_WELL_KNOWN_PATH,
    RESOURCE_ENV_VAR,
    SCOPE_SOURCE_ENV_VAR,
    TAG_SCOPES_ENV_VAR_PREFIX,
    XAA_EXCHANGE_AUDIENCE_ENV_VAR,
    XAA_REQUIRED_ENV_VARS,
    XAA_SCOPES_ENV_VAR,
    XAA_TOKEN_AUDIENCE_ENV_VAR,
    XAA_TOKEN_ENDPOINT_AUTH_METHOD_ENV_VAR,
    XAA_TOKEN_URL_ENV_VAR,
    XAA_TRUSTED_ISSUER_ENV_VAR,
    get_workload_mcp_oauth_routes,
    mcp_enable_unauthenticated_well_known_route_value,
    mcp_oauth_metadata_env_vars,
    mcp_tag_scope_env_vars,
    oauth_and_well_known_env_vars,
    validate_cross_application_access_env,
)

TRUSTED_ISSUER = "https://foo/bar/issuer"
EXCHANGE_AUDIENCE = "https://foo/bar/token_exchange_audience"
TOKEN_URL = "https://foo/bar/token"
TOKEN_AUDIENCE = "https://foo/bar/token_request_audience"


@pytest.fixture(autouse=True)
def _without_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate from the developer's own .env.

    Every setting now comes from the environment, so a populated shell would
    otherwise decide what these assertions see.
    """
    for name in (
        ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR,
        *OAUTH_METADATA_ENV_VARS,
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def complete_xaa_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(XAA_TRUSTED_ISSUER_ENV_VAR, TRUSTED_ISSUER)
    monkeypatch.setenv(XAA_EXCHANGE_AUDIENCE_ENV_VAR, EXCHANGE_AUDIENCE)
    monkeypatch.setenv(XAA_TOKEN_URL_ENV_VAR, TOKEN_URL)
    monkeypatch.setenv(XAA_SCOPES_ENV_VAR, "scope")


class TestOAuthMetadataEnvVars:
    def test_nothing_is_forwarded_when_nothing_is_configured(self) -> None:
        assert mcp_oauth_metadata_env_vars() == []

    def test_registered_fields_are_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(RESOURCE_ENV_VAR, "https://resource")
        monkeypatch.setenv(AUTHORIZATION_SERVERS_ENV_VAR, "https://as1,https://as2")
        monkeypatch.setenv(SCOPE_SOURCE_ENV_VAR, "tags")

        assert mcp_oauth_metadata_env_vars() == [
            {"name": RESOURCE_ENV_VAR, "value": "https://resource"},
            {
                "name": AUTHORIZATION_SERVERS_ENV_VAR,
                "value": "https://as1,https://as2",
            },
            {"name": SCOPE_SOURCE_ENV_VAR, "value": "tags"},
        ]

    def test_values_are_forwarded_verbatim(
        self, complete_xaa_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The server parses these; nothing here reshapes them."""
        monkeypatch.setenv(XAA_SCOPES_ENV_VAR, " dr.impersonation , dr.read ")

        forwarded = {var["name"]: var["value"] for var in mcp_oauth_metadata_env_vars()}

        assert forwarded[XAA_SCOPES_ENV_VAR] == "dr.impersonation , dr.read"

    def test_optional_xaa_settings_are_included_when_set(
        self, complete_xaa_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(XAA_TOKEN_AUDIENCE_ENV_VAR, TOKEN_AUDIENCE)
        monkeypatch.setenv(XAA_TOKEN_ENDPOINT_AUTH_METHOD_ENV_VAR, "client_secret_jwt")

        names = [var["name"] for var in mcp_oauth_metadata_env_vars()]

        assert names == [
            XAA_TRUSTED_ISSUER_ENV_VAR,
            XAA_EXCHANGE_AUDIENCE_ENV_VAR,
            XAA_TOKEN_URL_ENV_VAR,
            XAA_TOKEN_AUDIENCE_ENV_VAR,
            XAA_SCOPES_ENV_VAR,
            XAA_TOKEN_ENDPOINT_AUTH_METHOD_ENV_VAR,
        ]

    def test_optional_xaa_settings_are_omitted_when_unset(
        self, complete_xaa_env: None
    ) -> None:
        names = [var["name"] for var in mcp_oauth_metadata_env_vars()]

        assert XAA_TOKEN_AUDIENCE_ENV_VAR not in names
        assert XAA_TOKEN_ENDPOINT_AUTH_METHOD_ENV_VAR not in names


class TestCrossApplicationAccessValidation:
    def test_nothing_configured_is_valid(self) -> None:
        validate_cross_application_access_env()

    def test_complete_configuration_is_valid(self, complete_xaa_env: None) -> None:
        validate_cross_application_access_env()

    @pytest.mark.parametrize("omitted", XAA_REQUIRED_ENV_VARS)
    def test_a_partial_block_fails_the_deployment(
        self,
        complete_xaa_env: None,
        monkeypatch: pytest.MonkeyPatch,
        omitted: str,
    ) -> None:
        """Silently publishing metadata without the block hid this mistake before."""
        monkeypatch.delenv(omitted)

        with pytest.raises(ValueError, match=omitted):
            validate_cross_application_access_env()

    def test_a_blank_value_counts_as_unset(
        self, complete_xaa_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(XAA_TOKEN_URL_ENV_VAR, "   ")

        with pytest.raises(ValueError, match=XAA_TOKEN_URL_ENV_VAR):
            validate_cross_application_access_env()

    def test_the_forwarding_path_validates(
        self, complete_xaa_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The check has to sit on the path both hosting modes take."""
        monkeypatch.delenv(XAA_TOKEN_URL_ENV_VAR)

        with pytest.raises(ValueError, match=XAA_TOKEN_URL_ENV_VAR):
            mcp_oauth_metadata_env_vars()


class TestUnauthenticatedWellKnownRouteFlag:
    def test_defaults_to_false(self) -> None:
        assert mcp_enable_unauthenticated_well_known_route_value() == "false"

    @pytest.mark.parametrize(
        ("env_value", "expected"),
        [
            ("true", "true"),
            ("TRUE", "true"),
            ("  True  ", "true"),
            ("1", "true"),
            ("yes", "true"),
            ("on", "true"),
            ("false", "false"),
            ("0", "false"),
            ("no", "false"),
            ("banana", "false"),
        ],
    )
    def test_accepted_spellings_are_normalized(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: str
    ) -> None:
        """The value is normalized before it reaches the container."""
        monkeypatch.setenv(ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR, env_value)

        assert mcp_enable_unauthenticated_well_known_route_value() == expected

    def test_the_flag_is_not_a_metadata_setting(self) -> None:
        """It is server behaviour, and never published in the document."""
        assert ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR not in (
            OAUTH_METADATA_ENV_VARS
        )


class TestOAuthAndWellKnownEnvVars:
    def test_the_flag_leads_and_metadata_follows(
        self, complete_xaa_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR, "true")

        assert oauth_and_well_known_env_vars() == [
            {
                "name": ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR,
                "value": "true",
            },
            {"name": XAA_TRUSTED_ISSUER_ENV_VAR, "value": TRUSTED_ISSUER},
            {"name": XAA_EXCHANGE_AUDIENCE_ENV_VAR, "value": EXCHANGE_AUDIENCE},
            {"name": XAA_TOKEN_URL_ENV_VAR, "value": TOKEN_URL},
            {"name": XAA_SCOPES_ENV_VAR, "value": "scope"},
        ]

    def test_only_the_flag_when_no_metadata_is_configured(self) -> None:
        assert oauth_and_well_known_env_vars() == [
            {
                "name": ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR,
                "value": "false",
            },
        ]


class TestWorkloadOAuthRoutes:
    def test_no_routes_are_requested_when_the_flag_is_off(self) -> None:
        """None keeps every route on the gateway default of requiring auth."""
        assert get_workload_mcp_oauth_routes() is None

    def test_the_well_known_route_opts_out_when_the_flag_is_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENABLE_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENV_VAR, "true")

        assert get_workload_mcp_oauth_routes() == [
            {
                "path": OAUTH_PROTECTED_RESOURCE_WELL_KNOWN_PATH,
                "auth": "disabled",
            },
        ]


class TestTagScopeEnvVars:
    """Per-tag scope requirements are matched by prefix, not named individually."""

    def test_each_tag_variable_is_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(f"{TAG_SCOPES_ENV_VAR_PREFIX}DATABASE", "mcp:tools:write")
        monkeypatch.setenv(f"{TAG_SCOPES_ENV_VAR_PREFIX}READONLY", "mcp:tools:read")

        forwarded = mcp_tag_scope_env_vars()

        assert forwarded == [
            {
                "name": f"{TAG_SCOPES_ENV_VAR_PREFIX}DATABASE",
                "value": "mcp:tools:write",
            },
            {"name": f"{TAG_SCOPES_ENV_VAR_PREFIX}READONLY", "value": "mcp:tools:read"},
        ]

    def test_a_blank_variable_is_not_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GIVEN a blanked-out tag, THEN nothing is shipped and the guard lifts."""
        monkeypatch.setenv(f"{TAG_SCOPES_ENV_VAR_PREFIX}DATABASE", "   ")

        assert mcp_tag_scope_env_vars() == []

    def test_they_ride_along_with_the_metadata_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(f"{TAG_SCOPES_ENV_VAR_PREFIX}DATABASE", "mcp:tools:write")

        names = {env_var["name"] for env_var in mcp_oauth_metadata_env_vars()}

        assert f"{TAG_SCOPES_ENV_VAR_PREFIX}DATABASE" in names
