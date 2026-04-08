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
from pathlib import Path

from fastapi import APIRouter, HTTPException

# souls/ lives at the repo root — three levels above fastapi_server/app/api/v1/
SOULS_DIR = Path(__file__).parents[4] / "souls"

soul_router = APIRouter(prefix="/soul", tags=["soul"])


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
