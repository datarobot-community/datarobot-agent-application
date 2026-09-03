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

import contextlib
import dataclasses
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests

from mcp_server_clients.http_session import (
    create_datarobot_api_session,
)

BUILD_SUCCESS = "COMPLETED"
BUILD_FAILURES = frozenset({"FAILED", "CANCELLED"})
WORKLOAD_ARTIFACT_TYPE = "service"
DEFAULT_REQUEST_TIMEOUT_S = 60
# Tolerated consecutive poll failures (e.g. transient 502s) while a build runs.
MAX_TRANSIENT_POLL_FAILURES = 3


def _to_camel_case(snake_str: str) -> str:
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _to_wire(value: Any) -> Any:
    """Serialize spec dataclasses to the camelCase wire format, dropping None fields.

    Leaf values are passed through by reference (deliberately no deepcopy):
    environment entries may hold pulumi Outputs, which cannot be copied and
    are resolved downstream by their consumer.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            _to_camel_case(f.name): _to_wire(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if getattr(value, f.name) is not None
        }
    if isinstance(value, list):
        return [_to_wire(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_wire(item) for key, item in value.items()}
    return value


@dataclass
class CodeRefDatarobot:
    catalog_id: str
    catalog_version_id: str


@dataclass
class CodeRef:
    type: str
    provider: str
    datarobot: CodeRefDatarobot


@dataclass
class DockerfileProvided:
    path: str
    source: str = "provided"


@dataclass
class DockerfileGenerated:
    execution_environment_id: str
    execution_environment_version_id: str
    entrypoint: list[str]
    source: str = "generated"


@dataclass
class ImageBuildConfig:
    code_ref: CodeRef
    dockerfile: DockerfileProvided | DockerfileGenerated


@dataclass
class Container:
    name: str
    primary: bool
    port: int
    image_build_config: ImageBuildConfig
    environment_vars: list[dict[str, str]] = field(default_factory=list)
    routes: list[dict[str, str]] | None = None


@dataclass
class ContainerGroup:
    containers: list[Container]


@dataclass
class ArtifactSpecFromImageBuildConfig:
    container_groups: list[ContainerGroup]


@dataclass
class WorkloadArtifactSpecFromImageBuildConfig:
    name: str
    spec: ArtifactSpecFromImageBuildConfig
    type: str = WORKLOAD_ARTIFACT_TYPE

    def to_payload(self) -> dict:
        return _to_wire(self)


@dataclass
class ContainerImageUri:
    name: str
    primary: bool
    port: int
    image_uri: str
    environment_vars: list[dict[str, str]] = field(default_factory=list)
    # None omits the key so the image's own entrypoint is used.
    entrypoints: list[str] | None = None
    routes: list[dict[str, str]] | None = None


@dataclass
class ContainerGroupImageUri:
    containers: list[ContainerImageUri]


@dataclass
class ArtifactSpecFromImageUri:
    container_groups: list[ContainerGroupImageUri]


def _env_var_pulumi_args(entry: dict[str, str]) -> dict[str, str]:
    """Provider spelling of one env entry.

    Entries are built in REST wire form, where the credential reference is
    ``drCredentialId``; the pulumi provider names the same field
    ``credential_id``. Every other key is shared between the two.
    """
    return {
        ("credential_id" if key == "drCredentialId" else key): value
        for key, value in entry.items()
    }


@dataclass
class WorkloadArtifactSpecFromImageUri:
    name: str
    spec: ArtifactSpecFromImageUri
    type: str = WORKLOAD_ARTIFACT_TYPE

    def to_pulumi_args(self) -> dict:
        """Arguments for ``pulumi_datarobot.Artifact`` — not the REST payload.

        This spec's only consumer is the pulumi provider, which validates a
        typed snake_case spec. The camelCase wire format ``to_payload`` emits
        elsewhere happens to overlap it for most fields, but the differences
        are silently fatal: ``drCredentialId`` is not the provider's
        ``credential_id``, so credential-backed env vars would arrive under a
        key the provider does not know and be dropped.
        """
        return {
            "name": self.name,
            "type": self.type,
            "spec": {
                "container_groups": [
                    {
                        "containers": [
                            self._container_args(container)
                            for container in group.containers
                        ]
                    }
                    for group in self.spec.container_groups
                ]
            },
        }

    @staticmethod
    def _container_args(container: ContainerImageUri) -> dict[str, Any]:
        args: dict[str, Any] = {
            "name": container.name,
            "primary": container.primary,
            "port": container.port,
            "image_uri": container.image_uri,
            "environment_vars": [
                _env_var_pulumi_args(entry) for entry in container.environment_vars
            ],
        }
        if container.entrypoints is not None:
            args["entrypoints"] = container.entrypoints
        if container.routes is not None:
            # path/auth are spelled the same on both wires. Provider releases
            # that predate route support reject the key at preview time.
            args["routes"] = container.routes
        return args


class WorkloadClient:
    def __init__(
        self,
        endpoint: str,
        token: str,
        timeout_s: int = DEFAULT_REQUEST_TIMEOUT_S,
    ) -> None:
        self._base = endpoint.rstrip("/")
        self._timeout_s = timeout_s
        self._session = create_datarobot_api_session(
            token,
            default_headers={"Content-Type": "application/json"},
        )

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        """raise_for_status that surfaces the response body in the error.
        The Workload API returns actionable validation detail (e.g. which field
        was rejected) in the 4xx body; the default requests message drops it.
        """
        if resp.status_code >= 400:
            body = resp.text[:2000]
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason} for {resp.request.method} {resp.url}\n{body}",
                response=resp,
            )

    def create_artifact(self, spec: WorkloadArtifactSpecFromImageBuildConfig) -> str:
        payload = spec.to_payload()
        resp = self._session.post(
            self._url("/artifacts/"), json=payload, timeout=self._timeout_s
        )
        self._raise_for_status(resp)
        return resp.json()["id"]

    def delete_artifact(self, artifact_id: str) -> None:
        resp = self._session.delete(
            self._url(f"/artifacts/{artifact_id}"), timeout=self._timeout_s
        )
        # 404: already gone. 409: the platform retains artifacts that back a
        # live workload's revision history and refuses to delete them until the
        # workload itself is deleted — treat as released so replacements (e.g.
        # source-change redeploys) don't fail; `pulumi destroy` deletes the
        # workload first, so full teardown still deletes artifacts for real.
        if resp.status_code in (404, 409):
            return
        self._raise_for_status(resp)

    def trigger_build(self, artifact_id: str) -> list[str]:
        resp = self._session.post(
            self._url(f"/artifacts/{artifact_id}/builds"), timeout=self._timeout_s
        )
        self._raise_for_status(resp)
        data = resp.json()
        return data.get("buildIds") or data.get("build_ids") or []

    def get_build(self, artifact_id: str, build_id: str) -> dict:
        resp = self._session.get(
            self._url(f"/artifacts/{artifact_id}/builds/{build_id}"),
            timeout=self._timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    def get_build_logs(self, artifact_id: str, build_id: str) -> str:
        resp = self._session.get(
            self._url(f"/artifacts/{artifact_id}/builds/{build_id}/logs"),
            timeout=self._timeout_s,
        )
        resp.raise_for_status()
        return resp.text

    def wait_for_build(
        self,
        artifact_id: str,
        build_id: str,
        *,
        timeout_s: int,
        interval_s: int,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> str:
        deadline = now() + timeout_s
        last_status = "UNKNOWN"
        transient_failures = 0
        while True:
            try:
                last_status = str(
                    self.get_build(artifact_id, build_id).get("status", "UNKNOWN")
                )
                transient_failures = 0
            except requests.RequestException:
                transient_failures += 1
                if transient_failures >= MAX_TRANSIENT_POLL_FAILURES:
                    raise
            else:
                if last_status == BUILD_SUCCESS:
                    return last_status
                if last_status in BUILD_FAILURES:
                    logs = ""
                    try:
                        logs = self.get_build_logs(artifact_id, build_id)
                    except requests.RequestException:
                        pass
                    raise RuntimeError(
                        f"build {build_id} {last_status}\n{logs[-4000:]}"
                    )
            if now() >= deadline:
                raise TimeoutError(
                    f"build {build_id} not done after {timeout_s}s (last={last_status})"
                )
            sleep(interval_s)


def _create_and_build_artifact(
    client: WorkloadClient,
    spec: WorkloadArtifactSpecFromImageBuildConfig,
    build_timeout_s: int,
    build_interval_s: int = 10,
) -> str:
    artifact_id = client.create_artifact(spec)
    try:
        build_ids = client.trigger_build(artifact_id)
        if not build_ids:
            raise RuntimeError("no build id returned from trigger_build")
        client.wait_for_build(
            artifact_id,
            build_ids[0],
            timeout_s=build_timeout_s,
            interval_s=build_interval_s,
        )
    except BaseException:
        # The dynamic provider's create() never returns when this raises, so
        # Pulumi records no state for the artifact and would never delete it.
        # Best-effort cleanup; never mask the failure that got us here.
        with contextlib.suppress(Exception):
            client.delete_artifact(artifact_id)
        raise
    return artifact_id


def _image_build_spec(
    *,
    artifact_name: str,
    catalog_id: str,
    catalog_version_id: str,
    dockerfile: DockerfileProvided | DockerfileGenerated,
    container_name: str,
    container_port: int,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]] | None,
) -> WorkloadArtifactSpecFromImageBuildConfig:
    container = Container(
        name=container_name,
        primary=True,
        port=container_port,
        image_build_config=ImageBuildConfig(
            code_ref=CodeRef(
                type="datarobot",
                provider="datarobot",
                datarobot=CodeRefDatarobot(
                    catalog_id=catalog_id, catalog_version_id=catalog_version_id
                ),
            ),
            dockerfile=dockerfile,
        ),
        environment_vars=environment_vars,
        routes=routes,
    )
    return WorkloadArtifactSpecFromImageBuildConfig(
        name=artifact_name,
        spec=ArtifactSpecFromImageBuildConfig(
            container_groups=[ContainerGroup(containers=[container])]
        ),
    )


def build_artifact_with_provided_dockerfile(
    *,
    workload_api_endpoint: str,
    workload_api_token: str,
    artifact_name: str,
    catalog_id: str,
    catalog_version_id: str,
    dockerfile_relative_path: str,
    container_name: str,
    container_port: int,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]] | None,
    build_timeout_s: int,
) -> str:
    artifact_spec = _image_build_spec(
        artifact_name=artifact_name,
        catalog_id=catalog_id,
        catalog_version_id=catalog_version_id,
        dockerfile=DockerfileProvided(path=dockerfile_relative_path),
        container_name=container_name,
        container_port=container_port,
        environment_vars=environment_vars,
        routes=routes,
    )
    client = WorkloadClient(endpoint=workload_api_endpoint, token=workload_api_token)
    return _create_and_build_artifact(client, artifact_spec, build_timeout_s)


def build_artifact_with_generated_dockerfile(
    *,
    workload_api_endpoint: str,
    workload_api_token: str,
    artifact_name: str,
    catalog_id: str,
    catalog_version_id: str,
    execution_environment_id: str,
    execution_environment_version_id: str,
    entrypoint: list[str],
    container_name: str,
    container_port: int,
    environment_vars: list[dict[str, str]],
    routes: list[dict[str, str]] | None,
    build_timeout_s: int,
) -> str:
    artifact_spec = _image_build_spec(
        artifact_name=artifact_name,
        catalog_id=catalog_id,
        catalog_version_id=catalog_version_id,
        dockerfile=DockerfileGenerated(
            execution_environment_id=execution_environment_id,
            execution_environment_version_id=execution_environment_version_id,
            entrypoint=entrypoint,
        ),
        container_name=container_name,
        container_port=container_port,
        environment_vars=environment_vars,
        routes=routes,
    )
    client = WorkloadClient(endpoint=workload_api_endpoint, token=workload_api_token)
    return _create_and_build_artifact(client, artifact_spec, build_timeout_s)


def build_artifact_from_image_uri(
    *,
    artifact_name: str,
    container_name: str,
    container_port: int,
    image_uri: str,
    environment_vars: list[dict[str, str]] | None = None,
    entrypoints: list[str] | None = None,
    routes: list[dict[str, str]] | None = None,
) -> WorkloadArtifactSpecFromImageUri:
    container = ContainerImageUri(
        name=container_name,
        primary=True,
        port=container_port,
        image_uri=image_uri,
        environment_vars=environment_vars if environment_vars is not None else [],
        entrypoints=entrypoints,
        routes=routes,
    )
    return WorkloadArtifactSpecFromImageUri(
        name=artifact_name,
        spec=ArtifactSpecFromImageUri(
            container_groups=[ContainerGroupImageUri(containers=[container])]
        ),
    )
