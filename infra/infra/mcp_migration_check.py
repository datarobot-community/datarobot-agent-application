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
"""Stop a deploy that would delete the MCP server this template no longer includes.

Older versions of this template bundled an MCP server in mcp_server/. This version
doesn't, so the next deploy of an app that had one deletes that server from DataRobot,
and the agent loses its tools. This check reads the Pulumi stack, not git: while the
stack still holds the old server's resources (named "[mcp_server] ..."), every deploy
stops before anything changes and lists them, until MCP_MIGRATION_CONFIRMED=1 is set.
A confirmed deploy lists what a full deploy deletes. New apps, and apps whose stack no longer has
the old server, pass. See docs/mcp-migration.md.

How it runs: nothing calls it by name. infra/__main__.py imports every module in
infra/infra/ (import_infra_modules), and this module does its work at import time, at the
bottom of the file. So it runs whenever Pulumi runs the program: `pulumi preview` and
`pulumi up` (twice: the preview, then the update). That is every deploy command:
`dr run deploy`, `dr start` and `task deploy-dev` (a targeted `pulumi up`),
`dr run infra:up-yes`, `task infra:up`, and CI. `pulumi refresh` and `pulumi destroy`
don't run the program, so it never blocks them.

Temporary: remove this file once apps have moved past this template version.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pulumi

CONFIRM_ENV = "MCP_MIGRATION_CONFIRMED"
OLD_SERVER = "[mcp_server]"
SHOWN = 10  # resources listed by name; the rest are counted

STOP_MESSAGE = """\
MCP migration: deploy stopped. Nothing changed.

This version of the template no longer includes the MCP server (the
mcp_server/ folder): MCP servers now run as standalone apps. Your deployed app
still has the old one:
{resources}
This deploy would delete it, with its settings and credentials, and your agent
would lose its MCP tools.

Before you deploy:
  1. Move your MCP tools to a standalone MCP server, and set MCP_DEPLOYMENT_ID
     in .env. Or decide that you don't need them. See docs/mcp-migration.md.
  2. Add MCP_MIGRATION_CONFIRMED=1 to .env (in CI, set it in the environment).
     Then run a full deploy once: dr run deploy
     (`dr start` can't remove the old server.)

To keep the old server in this app instead, see docs/mcp-migration.md."""

CONFIRMED_MESSAGE = """\
MCP migration: MCP_MIGRATION_CONFIRMED is set. A full deploy (dr run deploy)
deletes the old MCP server from DataRobot, with its settings and credentials,
and your agent loses its MCP tools. The old server:
{resources}"""

DONE_MESSAGE = (
    "MCP migration: the old MCP server is gone from this app. "
    "You can remove MCP_MIGRATION_CONFIRMED from .env."
)


def confirmed() -> bool:
    return os.environ.get(CONFIRM_ENV, "").strip().lower() in ("1", "true", "yes")


def stack_resource_urns() -> list[str] | None:
    """The URNs of the resources in this stack's last saved state, or None when it can't
    be read. Resources the stack only reads (marked external), such as DataRobot's shared
    execution environments, are left out: a deploy never deletes them."""
    pulumi_cli = shutil.which("pulumi")
    if pulumi_cli is None:
        return None
    try:
        # A full path and close_fds=False let Python start pulumi with posix_spawn, not
        # fork. Forking while Pulumi's gRPC client runs makes gRPC log "FD from fork
        # parent still in poll list" into the deploy's output.
        export = subprocess.run(
            [pulumi_cli, "stack", "export", "--stack", pulumi.get_stack()],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            close_fds=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if export.returncode != 0:
        return None
    try:
        resources = (
            json.loads(export.stdout).get("deployment", {}).get("resources") or []
        )
    except (ValueError, AttributeError):
        return None
    return [
        str(resource.get("urn", ""))
        for resource in resources
        if not resource.get("external")
    ]


def resource_lines(names: list[str]) -> str:
    lines = [f"  - {name}" for name in names[:SHOWN]]
    if len(names) > SHOWN:
        lines.append(f"  - ...and {len(names) - SHOWN} more")
    return "\n".join(lines)


def stop_message() -> str | None:
    """The message that stops this deploy, or None to let it continue."""
    if (Path(__file__).parent / "mcp_server.py").exists():
        return None  # the app still has the MCP server: nothing is deleted
    urns = stack_resource_urns()
    if urns is None:
        pulumi.log.warn("MCP migration check skipped: could not read the Pulumi stack.")
        return None
    # A URN ends with the resource's name: "urn:pulumi:<stack>::<project>::<type>::<name>".
    old = sorted({urn.rsplit("::", 1)[-1] for urn in urns if OLD_SERVER in urn})
    if not old:
        if confirmed():
            pulumi.log.info(DONE_MESSAGE)
        return None
    if confirmed():
        pulumi.log.warn(CONFIRMED_MESSAGE.format(resources=resource_lines(old)))
        return None
    return STOP_MESSAGE.format(resources=resource_lines(old))


_message = stop_message()
if _message:
    pulumi.log.error(_message)
    sys.exit(1)
