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
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pulumi_datarobot
import yaml
from yaml import YAMLError

logger = logging.getLogger(__name__)


class BaseDataClass:
    def to_dict_without_null_attribute(self) -> dict[str, Any]:
        return asdict(
            self,  # type: ignore[call-overload]  # pyright: ignore[reportArgumentType]
            dict_factory=lambda x: {k: v for k, v in x if v is not None},
        )

    def to_yaml_string(self) -> str:
        return yaml.safe_dump(self.to_dict_without_null_attribute())


@dataclass
class XAATokenExchangeParams(BaseDataClass):
    trusted_issuer: str
    audience: str

    @classmethod
    def from_dict(cls, dict_input: dict[str, str]) -> "XAATokenExchangeParams":
        return cls(dict_input["trusted_issuer"], dict_input["audience"])


@dataclass
class XAATokenRequestParams(BaseDataClass):
    token_url: str
    # audience can be None if it is not setup for AuthN & AuthZ check (as resource) in IdP.
    audience: str | None
    scopes: list[str]

    @classmethod
    def from_dict(cls, dict_input: dict[str, Any]) -> "XAATokenRequestParams":
        return cls(
            dict_input["token_url"], dict_input.get("audience"), dict_input["scopes"]
        )


@dataclass
class XAAMetadata(BaseDataClass):
    token_endpoint_auth_method: str
    token_exchange: XAATokenExchangeParams
    token_request: XAATokenRequestParams

    @classmethod
    def from_dict(cls, metadata_in_dict: dict[str, Any]) -> "XAAMetadata":
        return cls(
            metadata_in_dict["token_endpoint_auth_method"],
            XAATokenExchangeParams.from_dict(metadata_in_dict["token_exchange"]),
            XAATokenRequestParams.from_dict(metadata_in_dict["token_request"]),
        )


@dataclass
class MCPOAuthProtectedResourceMetadataConfig(BaseDataClass):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str]
    xaa_metadata: XAAMetadata | None

    @classmethod
    def from_dict(
        cls, metadata_in_dict: dict[str, Any]
    ) -> "MCPOAuthProtectedResourceMetadataConfig":
        xaa_metadata = (
            XAAMetadata.from_dict(metadata_in_dict["xaa_metadata"])
            if metadata_in_dict.get("xaa_metadata")
            else None
        )
        return cls(
            metadata_in_dict["resource"],
            metadata_in_dict["authorization_servers"],
            metadata_in_dict["scopes_supported"],
            xaa_metadata,
        )


def config_dir_path() -> Path:
    current_path = Path(os.path.dirname(__file__))
    return current_path.parent.parent / "mcp_server"


class MCPOAuthProtectedResourceMetadataConfigManager:
    def __init__(self):
        self.config_dir_path = config_dir_path()

    def get_metadata_config_path(self) -> Path:
        return (
            self.config_dir_path / "mcp_oauth_protected_resource_metadata_config.yaml"
        )

    def load_metadata_config(self) -> dict[str, Any]:
        return yaml.safe_load(
            self.get_metadata_config_path().read_text(encoding="utf-8")
        )

    def get_yaml_string_of_metadata(self) -> str | None:
        metadata_in_string = None
        try:
            metadata_dict = self.load_metadata_config()
            metadata = MCPOAuthProtectedResourceMetadataConfig.from_dict(metadata_dict)
            metadata_in_string = metadata.to_yaml_string()
        except FileNotFoundError:
            error_message = (
                "Failed to load MCP OAuth protected resource metadata "
                f"from {self.get_metadata_config_path()}"
            )
            logger.info(error_message)
        except (AttributeError, KeyError, TypeError):
            logger.exception("Failed to parse MCP metadata")
        except YAMLError:
            logger.exception("Failed to load MCP metadata")
        return metadata_in_string

    def get_pulumi_custom_model_runtime_parameter_value_args_of_mcp_metadata(
        self,
    ) -> pulumi_datarobot.CustomModelRuntimeParameterValueArgs | None:
        metadata_in_string = self.get_yaml_string_of_metadata()

        return (
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key="MCP_OAUTH_PROTECTED_RESOURCE_METADATA_CONFIG",
                type="string",
                value=metadata_in_string,
            )
            if metadata_in_string
            else None
        )
