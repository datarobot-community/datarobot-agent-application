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

from pathlib import Path
from typing import Any

import yaml

_CLI_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / ".datarobot" / "cli"
DOTENV_CLI_YAML = _CLI_CONFIG_DIR / "agent.yaml"


def _load_dotenv_cli_config() -> dict[str, Any]:
    with DOTENV_CLI_YAML.open(encoding="utf-8") as dotenv_file:
        config = yaml.safe_load(dotenv_file)
    assert isinstance(config, dict)
    return config


def _find_env_prompt(
    config: dict[str, Any], env: str, section: str = "root"
) -> dict[str, Any] | None:
    for prompt in config.get(section, []):
        if prompt.get("env") == env:
            return prompt
    return None


def _find_key_prompt(
    config: dict[str, Any], key: str, section: str
) -> dict[str, Any] | None:
    for prompt in config.get(section, []):
        if prompt.get("key") == key:
            return prompt
    return None


def _help_display_lines(help_text: str) -> list[str]:
    if "\n" in help_text:
        return [line for line in help_text.splitlines() if line]
    return [help_text]


def _iter_prompts(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    prompts: list[tuple[str, dict[str, Any]]] = []
    for section, entries in config.items():
        if not isinstance(entries, list):
            continue
        for prompt in entries:
            if isinstance(prompt, dict):
                prompts.append((section, prompt))
    return prompts


def test_dotenv_help_fits_standard_terminal() -> None:
    """All dotenv prompt help text should fit an 80-column terminal window."""
    config = _load_dotenv_cli_config()
    max_width = 78

    for section, prompt in _iter_prompts(config):
        help_text = prompt.get("help")
        if not isinstance(help_text, str):
            continue
        for line in _help_display_lines(help_text):
            assert len(line) <= max_width, (
                f"{DOTENV_CLI_YAML.name}[{section}]: help line exceeds "
                f"{max_width} columns ({len(line)}): {line!r}"
            )
