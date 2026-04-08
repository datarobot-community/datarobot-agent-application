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

import base64

import httpx

_GH_API = "https://api.github.com"
_GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubError(RuntimeError):
    """Raised when a GitHub API call fails. Carries the HTTP status and message."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _auth_headers(token: str) -> dict:
    return {**_GH_HEADERS, "Authorization": f"Bearer {token}"}


async def create_branch(repo: str, branch: str, base_branch: str, token: str) -> None:
    """Create a new branch off base_branch in the given repo."""
    headers = _auth_headers(token)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_GH_API}/repos/{repo}/git/ref/heads/{base_branch}",
            headers=headers,
        )
        if resp.status_code != 200:
            raise GitHubError(
                502,
                f"GitHub: could not resolve base branch '{base_branch}' — {resp.text}",
            )
        base_sha = resp.json()["object"]["sha"]

        resp = await client.post(
            f"{_GH_API}/repos/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        if resp.status_code not in (200, 201):
            raise GitHubError(
                502,
                f"GitHub: could not create branch '{branch}' — {resp.text}",
            )


async def commit_file(
    repo: str, branch: str, path: str, content: str, message: str, token: str
) -> None:
    """Create or update a single file on a GitHub branch."""
    headers = _auth_headers(token)
    encoded = base64.b64encode(content.encode()).decode()

    async with httpx.AsyncClient() as client:
        # Fetch existing file SHA if the file already exists on this branch.
        existing = await client.get(
            f"{_GH_API}/repos/{repo}/contents/{path}",
            headers=headers,
            params={"ref": branch},
        )
        payload: dict = {"message": message, "content": encoded, "branch": branch}
        if existing.status_code == 200:
            payload["sha"] = existing.json()["sha"]

        resp = await client.put(
            f"{_GH_API}/repos/{repo}/contents/{path}",
            headers=headers,
            json=payload,
        )
        if resp.status_code not in (200, 201):
            raise GitHubError(
                502,
                f"GitHub: could not commit '{path}' — {resp.text}",
            )
