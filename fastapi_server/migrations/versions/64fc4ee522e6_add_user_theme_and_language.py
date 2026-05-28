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

"""add_user_theme_and_language

Revision ID: 64fc4ee522e6
Revises: 4d5262be920d
Create Date: 2026-05-15 20:59:33.102680

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64fc4ee522e6"
down_revision: Union[str, Sequence[str], None] = "4d5262be920d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    is_postgres = op.get_bind().dialect.name == "postgresql"
    language_default = sa.text("'en'::language") if is_postgres else sa.text("'en'")
    theme_default = sa.text("'system'::theme") if is_postgres else sa.text("'system'")

    theme_enum = sa.Enum("dark", "light", "system", name="theme")
    language_enum = sa.Enum("en", "es", "fr", "ja", "ko", "pt", name="language")

    if is_postgres:
        theme_enum.create(op.get_bind(), checkfirst=True)
        language_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "user",
        sa.Column(
            "theme",
            theme_enum,
            nullable=False,
            server_default=theme_default,
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "language",
            language_enum,
            nullable=False,
            server_default=language_default,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "language")
    op.drop_column("user", "theme")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TYPE IF EXISTS "language"'))
        op.execute(sa.text("DROP TYPE IF EXISTS theme"))
