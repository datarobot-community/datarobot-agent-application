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

"""Populate user.identities when users are stored outside SQL relationships."""

from __future__ import annotations

from typing import Protocol

from app.users.identity import Identity
from app.users.user import User


class UserIdentitySource(Protocol):
    """Minimal identity-repo surface used to hydrate ``User.identities``."""

    async def list_by_user_id(self, user_id: int) -> list[Identity]: ...


async def attach_user_identities(
    user: User | None, identity_repo: UserIdentitySource
) -> User | None:
    """Populate ``user.identities`` from the identity repository."""
    if user is None or user.id is None:
        return user
    user.identities = await identity_repo.list_by_user_id(user.id)
    return user
