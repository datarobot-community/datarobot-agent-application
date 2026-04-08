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

import json
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.github import GitHubError, commit_file, create_branch

# souls/ lives at the repo root — four levels above fastapi_server/app/api/v1/
SOULS_DIR = Path(__file__).parents[4] / "souls"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # e.g. "datarobot-community/datarobot-agent-application"
SCAFFOLD_API_KEY = os.getenv("SCAFFOLD_API_KEY", "")

soul_router = APIRouter(prefix="/soul", tags=["soul"])


# ── Models ────────────────────────────────────────────────────────────────────


class SoulScaffoldRequest(BaseModel):
    soul_name: str
    soul_content: str
    tools: list[str]
    base_branch: str = "main"
    branch_name: str | None = None


class SoulScaffoldResponse(BaseModel):
    branch_name: str
    branch_url: str
    clone_instructions: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _list_souls() -> list[str]:
    """Return names of all available soul packs (directories containing SOUL.md)."""
    if not SOULS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in SOULS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "SOUL.md").exists()
    )


def _active_soul() -> str:
    active_file = SOULS_DIR / ".active"
    return active_file.read_text().strip() if active_file.exists() else "supply-chain"


def _check_scaffold_auth(authorization: str) -> None:
    """Raise 403 if SCAFFOLD_API_KEY is set and the header does not match."""
    if not SCAFFOLD_API_KEY:
        return
    if authorization != f"Bearer {SCAFFOLD_API_KEY}":
        raise HTTPException(status_code=403, detail="Invalid or missing scaffold API key.")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@soul_router.get("/active")
async def get_active_soul() -> dict:
    """Return the currently active soul pack and list of available packs."""
    name = _active_soul()
    tools_file = SOULS_DIR / name / "mcp-tools.json"
    tools: list[str] = (
        json.loads(tools_file.read_text()).get("tools", [])
        if tools_file.exists()
        else []
    )
    return {
        "active_soul": name,
        "available_souls": _list_souls(),
        "tools": tools,
    }


@soul_router.post("/swap/{name}")
async def swap_soul(name: str) -> dict:
    """Swap the active soul pack. Takes effect on the next agent request — no restart needed."""
    soul_dir = SOULS_DIR / name
    if not soul_dir.exists() or not (soul_dir / "SOUL.md").exists():
        raise HTTPException(
            status_code=404,
            detail=f"Soul '{name}' not found. Available: {_list_souls()}",
        )
    (SOULS_DIR / ".active").write_text(name)

    tools_file = soul_dir / "mcp-tools.json"
    tools: list[str] = (
        json.loads(tools_file.read_text()).get("tools", [])
        if tools_file.exists()
        else []
    )
    return {
        "active_soul": name,
        "available_souls": _list_souls(),
        "tools": tools,
        "message": f"Swapped to '{name}'. Next agent request will use this soul.",
    }


@soul_router.get("/templates")
async def list_templates() -> dict:
    """Return all built-in domain pack templates — name, full SOUL.md, and default tools.

    DR UI calls this to populate the domain pack picker and prefill the soul editor.
    """
    templates = []
    for name in _list_souls():
        soul_dir = SOULS_DIR / name
        soul_file = soul_dir / "SOUL.md"
        tools_file = soul_dir / "mcp-tools.json"
        templates.append({
            "name": name,
            "soul_content": soul_file.read_text() if soul_file.exists() else "",
            "tools": (
                json.loads(tools_file.read_text()).get("tools", [])
                if tools_file.exists()
                else []
            ),
        })
    return {"templates": templates}


@soul_router.get("/templates/{name}")
async def get_template(name: str) -> dict:
    """Return a single domain pack template — full SOUL.md content and default tools.

    DR UI calls this when the user selects a domain pack to prefill the soul editor.
    """
    soul_dir = SOULS_DIR / name
    if not soul_dir.exists() or not (soul_dir / "SOUL.md").exists():
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found.")
    tools_file = soul_dir / "mcp-tools.json"
    return {
        "name": name,
        "soul_content": (soul_dir / "SOUL.md").read_text(),
        "tools": (
            json.loads(tools_file.read_text()).get("tools", [])
            if tools_file.exists()
            else []
        ),
    }


@soul_router.post("/scaffold-branch", response_model=SoulScaffoldResponse)
async def scaffold_branch(
    request: SoulScaffoldRequest,
    authorization: str = Header(default=""),
) -> SoulScaffoldResponse:
    """Create a new Git branch pre-loaded with the given soul configuration.

    Called by the DR platform when the user clicks "Get Repo". Commits three files
    onto a new branch off `base_branch`:
      - souls/<soul_name>/SOUL.md
      - souls/<soul_name>/mcp-tools.json
      - souls/.active  (set to soul_name)

    Requires GITHUB_TOKEN and GITHUB_REPO to be set in the environment.
    Requires Authorization: Bearer <SCAFFOLD_API_KEY> if SCAFFOLD_API_KEY is set.
    """
    _check_scaffold_auth(authorization)

    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(
            status_code=501,
            detail="GITHUB_TOKEN and GITHUB_REPO must be configured to use scaffold-branch.",
        )

    branch = request.branch_name or f"soul/{request.soul_name}"
    soul_name = request.soul_name

    try:
        await create_branch(GITHUB_REPO, branch, request.base_branch, GITHUB_TOKEN)

        await commit_file(
            GITHUB_REPO, branch,
            f"souls/{soul_name}/SOUL.md",
            request.soul_content,
            f"soul: scaffold {soul_name} — SOUL.md",
            GITHUB_TOKEN,
        )

        await commit_file(
            GITHUB_REPO, branch,
            f"souls/{soul_name}/mcp-tools.json",
            json.dumps({"tools": request.tools}, indent=2),
            f"soul: scaffold {soul_name} — mcp-tools.json",
            GITHUB_TOKEN,
        )

        await commit_file(
            GITHUB_REPO, branch,
            "souls/.active",
            soul_name,
            f"soul: set .active → {soul_name}",
            GITHUB_TOKEN,
        )
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    branch_url = f"https://github.com/{GITHUB_REPO}/tree/{branch}"
    clone_url = f"https://github.com/{GITHUB_REPO}.git"

    return SoulScaffoldResponse(
        branch_name=branch,
        branch_url=branch_url,
        clone_instructions=f"git clone -b {branch} {clone_url}",
    )
