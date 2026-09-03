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
import asyncio
import inspect
import json
import logging

from app.telemetry.logging import (
    JsonFormatter,
    get_logger,
    init_logging,
    log_api_call,
)


def _make_record(msg: str) -> logging.LogRecord:
    return logging.getLogger("test.logger").makeRecord(
        "test.logger", logging.INFO, __file__, 1, msg, (), None
    )


def test_json_formatter_emits_levelname_not_level() -> None:
    # Regression test: the DataRobot OTel collector's severity_parser only reads
    # "levelname" (matching platform services' JSON logs), never "level" - every
    # JSON log line from this formatter was silently defaulted to INFO otherwise.
    formatted = json.loads(JsonFormatter().format(_make_record("hello")))
    assert formatted["levelname"] == "INFO"
    assert "level" not in formatted


def test_init_logging_defaults_to_json() -> None:
    assert inspect.signature(init_logging).parameters["format_type"].default == "json"


def test_get_logger_defaults_to_json() -> None:
    # log_api_call calls get_logger() with no explicit format_type - its default
    # must match init_logging's so its logs aren't silently downgraded to plaintext.
    assert inspect.signature(get_logger).parameters["format_type"].default == "json"


def test_get_logger_redacts_sensitive_fields() -> None:
    # Regression test: get_logger handlers must wrap their formatter with
    # RedactingFormatter like init_logging does, or access_token/refresh_token
    # extras are logged in cleartext.
    logger = get_logger("test.redaction")
    formatted = logger.handlers[0].formatter.format(  # type: ignore[union-attr]
        _make_record("token access_token=secret123")
    )
    assert "secret123" not in formatted
    assert "[REDACTED]" in formatted


def test_log_api_call_does_not_touch_root_logger() -> None:
    # Regression test: log_api_call used get_logger() with the default empty
    # name, which reconfigures the root logger and drops the redacting handlers
    # installed by init_logging for the whole app.
    init_logging()
    root_handlers = logging.getLogger().handlers[:]

    @log_api_call
    async def sample_call() -> None:
        return None

    asyncio.run(sample_call())
    assert logging.getLogger().handlers == root_handlers
