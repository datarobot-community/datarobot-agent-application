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

"""Agent provisioning via the Workload API runtime.

Serving-only: creates an image-build ``Artifact`` (or references one by URI)
plus a ``Workload`` — no ``CustomModel``/``Playground``/``LlmBlueprint``
anywhere in this module (Playground for this runtime is an explicit, deferred
follow-up; see docs/agent/deployment-runtimes.md). Selects one of two
deployment scenarios based on env vars; see ``provision_workload_agent()``'s
docstring for the exact precedence. Self-contained: everything specific to
this runtime lives here. Never checks ``ENABLE_AGENT_ON_WORKLOAD_API`` itself
-- the entry router is the only place that branches on it.

Both artifact scenarios go straight through ``pulumi_datarobot``'s native
``Artifact``/``Workload`` resources -- no HTTP client or dynamic provider of
our own. For the C2W scenario, ``pulumi_datarobot.ArtifactSourceArgs(dir=...)``
uploads the agent source directly; this module only assembles the container
env vars and the rest of the artifact spec around it.
"""

from __future__ import annotations

import json
import os
import shutil
import tomllib
from pathlib import Path
from typing import Any, Final

import pulumi
import pulumi_datarobot
from datarobot_pulumi_utils.pulumi import export

from . import base

WORKLOAD_CONTAINER_NAME: Final[str] = "agent"
DEFAULT_WORKLOAD_CONTAINER_PORT: Final[int] = 8080
RUN_SERVER_RELATIVE_PATH: Final[str] = "workload/run_server.sh"
# 2.5h. Agent images carry a full framework + ML dependency set, so a cold
# platform build takes considerably longer than a plain web-server image.
DEFAULT_BUILD_TIMEOUT_S: Final[int] = 9000
# Entrypoint for the platform-generated Dockerfile C2W build.
DEFAULT_GENERATED_ENTRYPOINT: Final[list[str]] = [
    "sh",
    RUN_SERVER_RELATIVE_PATH,
]
# Field holding the token inside a DataRobot api_token credential; the `key` of
# "dr-credential" env var references in Workload artifact specs.
DR_CREDENTIAL_API_TOKEN_KEY: Final[str] = "apiToken"
DEFAULT_WORKLOAD_CPU: Final[str] = "1"
# 1.5 GiB: room for an agent process (LLM client libraries, framework deps)
# without over-provisioning every deployment by default.
DEFAULT_WORKLOAD_MEMORY_BYTES: Final[int] = 1536 * 1024 * 1024
A2A_UNAUTHENTICATED_WELL_KNOWN_ARTIFACT_ROUTE: Final[dict[str, str]] = {
    "path": "/a2a/.well-known/agent-card.json",
    "auth": "optional",
}
# Entry-point group NAT resolves the agent's workflow through.
NAT_PLUGIN_ENTRY_POINT_GROUP: Final[str] = "nat.plugins"
# OTel collector base URL, forwarded from the deploy environment when set.
OTEL_ENDPOINT_ENV_VAR: Final[str] = "OTEL_EXPORTER_OTLP_ENDPOINT"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        message = f"{name} is required when ENABLE_AGENT_ON_WORKLOAD_API is set"
        pulumi.error(message)
        raise RuntimeError(message)
    return value


def _explicit_workload_entrypoint() -> list[str] | None:
    """Parse WORKLOAD_ENTRYPOINT (JSON list or comma-separated); None when unset."""
    raw = os.getenv("WORKLOAD_ENTRYPOINT", "").strip()
    if not raw:
        return None
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            message = f"WORKLOAD_ENTRYPOINT is not valid JSON: {exc}"
            pulumi.error(message)
            raise RuntimeError(message) from exc
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            message = "WORKLOAD_ENTRYPOINT JSON must be a list of strings"
            pulumi.error(message)
            raise RuntimeError(message)
        return parsed
    return [part.strip() for part in raw.split(",") if part.strip()]


def _resolve_generated_entrypoint() -> list[str]:
    return _explicit_workload_entrypoint() or list(DEFAULT_GENERATED_ENTRYPOINT)


def _resolve_container_port() -> int:
    return int(
        os.getenv("WORKLOAD_CONTAINER_PORT", str(DEFAULT_WORKLOAD_CONTAINER_PORT))
    )


def _readiness_probe() -> (
    pulumi_datarobot.ArtifactSpecContainerGroupContainerReadinessProbeArgs
):
    """Readiness probe for the agent's ``/health`` endpoint, on the resolved container port."""
    return pulumi_datarobot.ArtifactSpecContainerGroupContainerReadinessProbeArgs(
        path="/health", port=_resolve_container_port()
    )


def _workload_artifact_routes() -> (
    list[pulumi_datarobot.ArtifactSpecContainerGroupContainerRouteArgs] | None
):
    """Workload artifact routes derived from ``workflow.yaml`` A2A settings.

    When ``enable_unauthenticated_well_known_route`` is truthy, the platform must
    expose the well-known agent card path with optional auth so anonymous callers
    can fetch a redacted card.

    Returns ``None`` — not ``[]`` — when the flag is off, so the ``routes`` key is
    omitted from the spec entirely. Clusters can have route configuration
    disabled, and they reject an artifact that carries the key at all with::

        403 {"detail":"Route configuration is disabled on this cluster"}

    so an empty list is not a safe stand-in for omitting it.
    """
    if base.IS_A2A_UNAUTHENTICATED_WELL_KNOWN_ROUTE_ENABLED:
        return [
            pulumi_datarobot.ArtifactSpecContainerGroupContainerRouteArgs(
                path=A2A_UNAUTHENTICATED_WELL_KNOWN_ARTIFACT_ROUTE["path"],
                auth=A2A_UNAUTHENTICATED_WELL_KNOWN_ARTIFACT_ROUTE["auth"],
            )
        ]
    return None


def dr_credential_env_var(
    name: str, credential_id: Any
) -> pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs:
    """Workload artifact env var entry resolved from a DataRobot credential at runtime.

    The credential value itself never appears in the artifact spec or Pulumi
    state -- only its ID does, and the platform resolves the value at container
    start.
    """
    return pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
        name=name,
        source="dr-credential",
        dr_credential_id=credential_id,
        key=DR_CREDENTIAL_API_TOKEN_KEY,
    )


def _runtime_param_env_vars(
    params: list[pulumi_datarobot.CustomModelRuntimeParameterValueArgs],
) -> list[pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs]:
    """Translate shared runtime parameters into Workload container env vars.

    | Source                                              | Workload mapping                    |
    |------------------------------------------------------|--------------------------------------|
    | ``type="credential"`` (session secret, Mem0 key, IDP JWK) | ``dr-credential`` reference   |
    | everything else (LLM/MCP params, ``IDP_AGENT_ID``, ``AGENT_GUNICORN_WORKER_TIMEOUT``, ``AGENT_MEMORY_SPACE_ID``) | plain ``name``/``value`` pair |

    ``CUSTOM_MODEL_WORKERS`` never reaches here — it's added only in
    ``deployment.py``, since ``base.build_shared_agent_runtime_parameters()``
    excludes it (no Workload-container equivalent).
    """
    env_vars: list[
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs
    ] = []
    for param in params:
        key = str(param.key)
        if param.type == "credential":
            env_vars.append(dr_credential_env_var(key, param.value))
        else:
            env_vars.append(
                pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
                    name=key, value=param.value
                )
            )
    return env_vars


def _otel_endpoint_env_var() -> list[
    pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs
]:
    """``OTEL_EXPORTER_OTLP_ENDPOINT`` as a container env var, when set locally.

    The platform configures no OTel on a workload, and moderation guard metrics
    read this variable directly. Empty when unset. Auth headers are not
    forwarded -- they carry the API token, and the container builds its own.
    """
    endpoint = os.getenv(OTEL_ENDPOINT_ENV_VAR, "").strip()
    if not endpoint:
        return []
    pulumi.info(f"Workload container telemetry: {OTEL_ENDPOINT_ENV_VAR}={endpoint}")
    return [
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            name=OTEL_ENDPOINT_ENV_VAR, value=endpoint
        )
    ]


def _workload_environment_vars(
    shared_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> list[pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs]:
    return [
        # Pulls DATAROBOT_API_TOKEN from the local env into the workload. The
        # platform injects DATAROBOT_ENDPOINT and WORKLOAD_ID automatically, so
        # they must not be listed here.
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            source="api-key"
        ),
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs(
            name="WORKLOAD_CONTAINER_PORT", value=str(_resolve_container_port())
        ),
        *_otel_endpoint_env_var(),
        *_runtime_param_env_vars(shared_runtime_parameters),
    ]


def _create_image_uri_artifact(
    *,
    asset_name: str,
    image_uri: str,
    environment_vars: list[
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs
    ],
    entrypoints: list[str] | None,
) -> pulumi_datarobot.Artifact:
    """Build the ``pulumi_datarobot.Artifact`` arguments for a pre-built image.

    The pre-built-image scenario reaches the platform entirely through the
    Pulumi provider, so this payload is the whole integration — no HTTP client,
    no artifact build to wait on. Keys are the Workload API's own wire format
    and are forwarded by the provider as-is (see the module docstring).
    """
    pulumi.info(
        f"Workload image build: pre-built image from personal registry {image_uri}"
    )
    return pulumi_datarobot.Artifact(
        asset_name + " Workload Artifact [Image URI]",
        name=asset_name,
        description=f"Agent workload artifact built from pre-built image {image_uri}",
        type="agent",
        status="locked",
        spec=pulumi_datarobot.ArtifactSpecArgs(
            a2a_enabled=True,
            container_groups=[
                pulumi_datarobot.ArtifactSpecContainerGroupArgs(
                    containers=[
                        pulumi_datarobot.ArtifactSpecContainerGroupContainerArgs(
                            name=WORKLOAD_CONTAINER_NAME,
                            primary=True,
                            image_uri=image_uri,
                            entrypoints=entrypoints,
                            port=_resolve_container_port(),
                            routes=_workload_artifact_routes(),
                            environment_vars=environment_vars,
                            readiness_probe=_readiness_probe(),
                        )
                    ]
                ),
            ],
        ),
    )


def _create_generated_image_artifact(
    *,
    asset_name: str,
    application_path: str,
    environment_vars: list[
        pulumi_datarobot.ArtifactSpecContainerGroupContainerEnvironmentVarArgs
    ],
    execution_environment: pulumi_datarobot.ExecutionEnvironment,
) -> pulumi_datarobot.Artifact:
    pulumi.info(
        "Workload image build: platform-generated Dockerfile "
        "(execution environment aligned with the Custom Models runtime)"
    )
    return pulumi_datarobot.Artifact(
        asset_name + " Workload Artifact [Generated Dockerfile]",
        name=asset_name,
        description="Agent workload artifact built from local source via generated Dockerfile",
        type="agent",
        status="locked",
        source=pulumi_datarobot.ArtifactSourceArgs(
            dir=application_path,
            # wait_for_build defaults to True
        ),
        opts=pulumi.ResourceOptions(depends_on=[execution_environment]),
        spec=pulumi_datarobot.ArtifactSpecArgs(
            a2a_enabled=True,
            container_groups=[
                pulumi_datarobot.ArtifactSpecContainerGroupArgs(
                    containers=[
                        pulumi_datarobot.ArtifactSpecContainerGroupContainerArgs(
                            name=WORKLOAD_CONTAINER_NAME,
                            primary=True,
                            port=_resolve_container_port(),
                            routes=_workload_artifact_routes(),
                            environment_vars=environment_vars,
                            image_build_config=pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigArgs(
                                dockerfile=pulumi_datarobot.ArtifactSpecContainerGroupContainerImageBuildConfigDockerfileArgs(
                                    source="generated",
                                    execution_environment_id=execution_environment.id,
                                    execution_environment_version_id=execution_environment.version_id,
                                    entrypoints=_resolve_generated_entrypoint(),
                                ),
                            ),
                            readiness_probe=_readiness_probe(),
                        )
                    ]
                )
            ],
        ),
    )


def _create_workload(
    *,
    asset_name: str,
    artifact_id: pulumi.Input[str],
    depends_on: list[Any],
) -> pulumi_datarobot.Workload:
    return pulumi_datarobot.Workload(
        asset_name + " Workload",
        name=asset_name,
        artifact_id=artifact_id,
        importance=os.getenv("WORKLOAD_IMPORTANCE", "high"),
        runtime=pulumi_datarobot.WorkloadRuntimeArgs(
            container_groups=[
                pulumi_datarobot.WorkloadRuntimeContainerGroupArgs(
                    replica_count=int(os.getenv("WORKLOAD_REPLICA_COUNT", "1")),
                    resource_bundles=["cpu.xlarge"],
                    containers=[
                        pulumi_datarobot.WorkloadRuntimeContainerGroupContainerArgs(
                            name=WORKLOAD_CONTAINER_NAME,
                            resource_allocation=pulumi_datarobot.WorkloadRuntimeContainerGroupContainerResourceAllocationArgs(
                                cpu=float(
                                    os.getenv("WORKLOAD_CPU", DEFAULT_WORKLOAD_CPU)
                                ),
                                # Integer bytes as a string ("1610612736"), or a
                                # human-readable quantity ("2Gi") -- both are accepted
                                # server-side (see ArtifactSpecContainerGroupContainer-
                                # ResourceAllocationArgs.memory's docstring).
                                memory=os.getenv(
                                    "WORKLOAD_MEMORY",
                                    str(DEFAULT_WORKLOAD_MEMORY_BYTES),
                                ),
                            ),
                        )
                    ],
                )
            ]
        ),
        opts=pulumi.ResourceOptions(
            depends_on=depends_on,
            delete_before_replace=False,
            retain_on_delete=False,
        ),
    )


def _export_workload_endpoints(
    asset_name: str, workload: pulumi_datarobot.Workload
) -> tuple[pulumi.Output[str], pulumi.Output[str] | None]:
    """Export workload IDs/endpoints; return (chat-completions endpoint, a2a endpoint | None)."""
    pulumi.export("Agent Workload Endpoint " + asset_name, workload.endpoint)
    pulumi.export("Agent Workload Id " + asset_name, workload.id)
    pulumi.export("Agent Workload Artifact Id " + asset_name, workload.artifact_id)

    completions_endpoint = workload.endpoint.apply(
        lambda endpoint: f"{endpoint.rstrip('/')}/chat/completions"
    )
    pulumi.export(
        "Agent Workload Chat Endpoint " + asset_name,
        completions_endpoint,
    )

    a2a_endpoint: pulumi.Output[str] | None = None
    if base.IS_A2A_SERVER_ENABLED:
        # Equivalent to the Custom Models path's `directAccess/a2a/` — no
        # `.well-known/agent-card.json` suffix, that's a client-side discovery
        # path under this route, not part of the endpoint we export.
        a2a_endpoint = workload.endpoint.apply(
            lambda endpoint: f"{endpoint.rstrip('/')}/a2a/"
        )

    return completions_endpoint, a2a_endpoint


def _build_runtime_parameter_exports(
    *,
    asset_name: str,
    application_name: str,
    workload: pulumi_datarobot.Workload,
    a2a_endpoint: pulumi.Output[str] | None,
) -> tuple[
    list[pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs],
    list[pulumi_datarobot.CustomModelRuntimeParameterValueArgs],
]:
    app_runtime_parameters = [
        pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
            key=application_name.upper() + "_WORKLOAD_ID",
            type="string",
            value=workload.id,
        ),
        pulumi_datarobot.ApplicationSourceRuntimeParameterValueArgs(
            key=application_name.upper() + "_ENDPOINT",
            type="string",
            value=workload.endpoint,
        ),
    ]
    agent_runtime_parameters = [
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=application_name.upper() + "_WORKLOAD_ID",
            type="string",
            value=workload.id,
        ),
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
            key=application_name.upper() + "_ENDPOINT",
            type="string",
            value=workload.endpoint,
        ),
    ]
    if a2a_endpoint is not None:
        agent_runtime_parameters.append(
            pulumi_datarobot.CustomModelRuntimeParameterValueArgs(
                key=application_name.upper() + "_A2A_ENDPOINT",
                type="string",
                value=a2a_endpoint,
            ),
        )
    export(
        application_name.upper() + "_WORKLOAD_ID",
        workload.id,
    )
    return app_runtime_parameters, agent_runtime_parameters


def _provision_from_image_uri(
    image_uri: str,
    shared_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> dict[str, Any]:
    pulumi.info(
        f"Workload scenario: pre-built image from personal registry ({image_uri})."
    )

    artifact = _create_image_uri_artifact(
        asset_name=base.agent_asset_name,
        image_uri=image_uri,
        environment_vars=_workload_environment_vars(shared_runtime_parameters),
        entrypoints=_explicit_workload_entrypoint(),
    )

    workload = _create_workload(
        asset_name=base.agent_asset_name,
        artifact_id=artifact.artifact_id,
        depends_on=[artifact],
    )

    pulumi.export("Agent Workload Image URI " + base.agent_asset_name, image_uri)
    completions_endpoint, a2a_endpoint = _export_workload_endpoints(
        base.agent_asset_name, workload
    )
    app_runtime_parameters, agent_runtime_parameters = _build_runtime_parameter_exports(
        asset_name=base.agent_asset_name,
        application_name=base.agent_application_name,
        workload=workload,
        a2a_endpoint=a2a_endpoint,
    )

    return {
        "execution_environment": None,
        "deployment": None,
        "workload": workload,
        "custom_model": None,
        "agent_deployment_id": None,
        "prediction_environment": None,
        "registered_model_args": None,
        "deployment_args": None,
        "agent_serving_endpoint": completions_endpoint,
        "agent_a2a_endpoint": a2a_endpoint,
        "app_runtime_parameters": app_runtime_parameters,
        "agent_runtime_parameters": agent_runtime_parameters,
    }


def _render_entry_points(groups: dict[str, dict[str, str]]) -> str:
    """Entry-point groups as the `entry_points.txt` INI that importlib.metadata reads."""
    lines = []
    for group, entries in sorted(groups.items()):
        lines.append(f"[{group}]")
        lines += [f"{name} = {target}" for name, target in sorted(entries.items())]
        lines.append("")
    return "\n".join(lines)


def _ensure_agent_has_entrypoint(application_path: Path) -> None:
    """Write the entry-point metadata the container resolves the workflow through.

    Nothing installs the agent inside the image and the application root is
    read-only at run time, so ``importlib.metadata`` needs a ``.dist-info`` sitting
    next to the package; ``run_server.sh`` puts the root on ``PYTHONPATH``.

    Rewritten from ``pyproject.toml`` on every deploy, so it cannot go stale, and
    byte-identical for unchanged input, so it does not disturb the source hash.
    """
    pyproject = application_path / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        name, version = project["name"], project["version"]
        entry_points = project["entry-points"]
        if NAT_PLUGIN_ENTRY_POINT_GROUP not in entry_points:
            raise KeyError(NAT_PLUGIN_ENTRY_POINT_GROUP)
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        message = (
            f"Could not read a [{NAT_PLUGIN_ENTRY_POINT_GROUP}] entry point from "
            f"{pyproject}: {exc!r}. The workload resolves the agent's workflow "
            f"through it, so declare one under "
            f"[project.entry-points.'{NAT_PLUGIN_ENTRY_POINT_GROUP}']."
        )
        pulumi.error(message)
        raise RuntimeError(message) from exc

    dist_info = application_path / f"{name}-{version}.dist-info"
    # A version bump would otherwise leave a second distribution of the same name
    # on sys.path, and importlib.metadata resolves whichever it sees first.
    for stale in application_path.glob(f"{name}-*.dist-info"):
        if stale != dist_info:
            shutil.rmtree(stale)
    dist_info.mkdir(exist_ok=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
    )
    (dist_info / "entry_points.txt").write_text(
        _render_entry_points(entry_points), encoding="utf-8"
    )


def _provision_from_source_bundle(
    shared_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> dict[str, Any]:
    pulumi.info(
        "Workload scenario: C2W with platform-generated Dockerfile "
        "(dropin execution environment)."
    )

    _ensure_agent_has_entrypoint(base.agent_application_path)

    # use_cases=["customModel"] only: this EE is used purely as the base
    # image for the generated Dockerfile build, never for Playground's
    # codespace fallback (which doesn't exist in Workload API mode).
    execution_environment = base.resolve_agent_execution_environment(
        asset_name=base.agent_asset_name + " [Workload Generated Dockerfile]",
        application_path=base.agent_application_path,
        use_cases=["customModel"],
    )

    artifact = _create_generated_image_artifact(
        asset_name=base.agent_asset_name,
        application_path=str(base.agent_application_path),
        environment_vars=_workload_environment_vars(shared_runtime_parameters),
        execution_environment=execution_environment,
    )

    workload = _create_workload(
        asset_name=base.agent_asset_name,
        artifact_id=artifact.artifact_id,
        depends_on=[artifact, execution_environment],
    )

    pulumi.export(
        "Agent Execution Environment ID " + base.agent_asset_name,
        execution_environment.id,
    )
    pulumi.export(
        "Agent Execution Environment Version ID " + base.agent_asset_name,
        execution_environment.version_id,
    )
    completions_endpoint, a2a_endpoint = _export_workload_endpoints(
        base.agent_asset_name, workload
    )
    app_runtime_parameters, agent_runtime_parameters = _build_runtime_parameter_exports(
        asset_name=base.agent_asset_name,
        application_name=base.agent_application_name,
        workload=workload,
        a2a_endpoint=a2a_endpoint,
    )

    return {
        "execution_environment": execution_environment,
        "deployment": None,
        "workload": workload,
        "custom_model": None,
        "agent_deployment_id": None,
        "prediction_environment": None,
        "registered_model_args": None,
        "deployment_args": None,
        "agent_serving_endpoint": completions_endpoint,
        "agent_a2a_endpoint": a2a_endpoint,
        "app_runtime_parameters": app_runtime_parameters,
        "agent_runtime_parameters": agent_runtime_parameters,
    }


def provision_workload_agent(
    shared_runtime_parameters: list[
        pulumi_datarobot.CustomModelRuntimeParameterValueArgs
    ],
) -> dict[str, Any]:
    """Provision the agent on the Workload API runtime.

    Serving-only: never creates ``CustomModel``/``Playground``/``LlmBlueprint``
    (see module docstring). Selects exactly one of two scenarios, in this
    precedence order:

    1. ``WORKLOAD_AGENT_IMAGE_URI`` set → pre-built image from a personal
       registry (``pulumi_datarobot.Artifact`` from an image URI + ``Workload``).
    2. else → C2W with a platform-generated Dockerfile and a dropin execution
       environment as the base image (execution environment + ``Artifact``
       built from local source + ``Workload``).

    Building the artifact out-of-band (``dr artifact`` CLI + a Pulumi stack
    that only creates the ``Workload`` from a pre-existing artifact ID) is
    intentionally not implemented here and is not a supported path.
    """
    _require_env("DATAROBOT_API_TOKEN")

    image_uri = os.getenv("WORKLOAD_AGENT_IMAGE_URI", "").strip()
    if image_uri:
        return _provision_from_image_uri(image_uri, shared_runtime_parameters)
    return _provision_from_source_bundle(shared_runtime_parameters)
