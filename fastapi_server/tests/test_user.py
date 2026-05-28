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
from pydantic import ValidationError

from app.users.user import LanguageEnum, ThemeEnum, User, UserCreate


class TestUserCreate:
    """Tests for UserCreate schema."""

    def test_empty_last_name_allowed(self) -> None:
        user = UserCreate(email="test@example.com", last_name="")
        assert user.last_name == ""

    def test_none_last_name_allowed(self) -> None:
        user = UserCreate(email="test@example.com", last_name=None)
        assert user.last_name is None

    def test_valid_last_name(self) -> None:
        user = UserCreate(email="test@example.com", last_name="Smith")
        assert user.last_name == "Smith"

    def test_last_name_max_length_enforced(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", last_name="A" * 51)


class TestUser:
    def test_empty_last_name_allowed(self) -> None:
        user = User(email="test@example.com", last_name="")
        assert user.last_name == ""

    def test_none_last_name_allowed(self) -> None:
        user = User(email="test@example.com", last_name=None)
        assert user.last_name is None


class TestLanguageEnum:
    @pytest.mark.parametrize(
        "locale,expected",
        [
            (None, LanguageEnum.en),
            ("en", LanguageEnum.en),
            ("en-US", LanguageEnum.en),
            ("EN", LanguageEnum.en),
            ("ja", LanguageEnum.ja),
            ("ja-JP", LanguageEnum.ja),
            ("fr", LanguageEnum.fr),
            ("fr-FR", LanguageEnum.fr),
            ("ko", LanguageEnum.ko),
            ("ko-KR", LanguageEnum.ko),
            ("pt-BR", LanguageEnum.pt),
            ("pt_BR", LanguageEnum.pt),
            ("es-419", LanguageEnum.es),
            ("es-ES", LanguageEnum.es),
            ("zh", LanguageEnum.en),  # unsupported → default
            ("xx", LanguageEnum.en),  # unknown → default
        ],
    )
    def test_from_locale(self, locale: str | None, expected: LanguageEnum) -> None:
        assert LanguageEnum.from_locale(locale) == expected


class TestThemeEnum:
    @pytest.mark.parametrize(
        "theme,expected",
        [
            (None, ThemeEnum.system),
            ("dark", ThemeEnum.dark),
            ("light", ThemeEnum.light),
            ("system", ThemeEnum.system),
            ("invalid", ThemeEnum.system),  # unknown → default
        ],
    )
    def test_from_theme(self, theme: str | None, expected: ThemeEnum) -> None:
        assert ThemeEnum.from_theme(theme) == expected
