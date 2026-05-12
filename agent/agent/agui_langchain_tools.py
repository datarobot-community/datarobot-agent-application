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

"""Map AG-UI ``RunAgentInput.tools`` to LangChain tools for the LangGraph agent."""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any

from ag_ui.core import Tool as AguiTool
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

logger = logging.getLogger(__name__)


def _safe_model_name(prefix: str) -> str:
    safe = re.sub(r"\W|^(?=\d)", "_", prefix, flags=re.ASCII)
    safe = safe.strip("_") or "tool"
    return f"{safe}_{uuid.uuid4().hex[:10]}"


def _fields_from_json_schema(schema: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    props = schema.get("properties")
    if not isinstance(props, dict):
        raise ValueError("JSON Schema must declare an object 'properties' map")
    required = set(schema.get("required") or [])
    fields: dict[str, tuple[Any, Any]] = {}
    for prop_name, sub in props.items():
        if not isinstance(sub, dict):
            continue
        desc = str(sub.get("description") or "")
        json_type = sub.get("type")
        if json_type == "string":
            py_type: Any = str
        elif json_type == "integer":
            py_type = int
        elif json_type == "number":
            py_type = float
        elif json_type == "boolean":
            py_type = bool
        elif json_type == "array":
            py_type = list[Any]
        elif json_type == "object":
            py_type = dict[str, Any]
        else:
            py_type = Any
        if prop_name in required:
            fields[prop_name] = (py_type, Field(description=desc))
        else:
            fields[prop_name] = (py_type | None, Field(default=None, description=desc))
    if not fields:
        raise ValueError("No usable properties in JSON Schema")
    return fields


def agui_tool_to_langchain(ag_tool: AguiTool) -> StructuredTool:
    """Build a LangChain ``StructuredTool`` from an AG-UI tool definition.

    The tool body returns JSON; front-end–executed tools still get server-side
    tool-call / tool-result events so the AG-UI client can run handlers and
    follow up in the same thread.
    """
    params = ag_tool.parameters
    use_fallback = False
    try:
        if isinstance(params, dict) and params.get("type") == "object":
            field_defs = _fields_from_json_schema(params)
            args_schema = create_model(  # type: ignore[call-overload]
                _safe_model_name(ag_tool.name), **field_defs
            )
        else:
            raise ValueError("parameters missing or not an object schema")
    except Exception as exc:
        use_fallback = True
        logger.debug("AG-UI tool %s: fallback args schema (%s)", ag_tool.name, exc)
        args_schema = create_model(  # type: ignore[call-overload]
            _safe_model_name(ag_tool.name),
            arguments=(
                str,
                Field(
                    default="{}",
                    description="JSON-encoded arguments object for this tool",
                ),
            ),
        )

    async def _run(**kwargs: Any) -> str:
        if use_fallback:
            raw = kwargs.get("arguments", "{}")
            return raw if isinstance(raw, str) else json.dumps(raw, default=str)
        return json.dumps(kwargs, default=str)

    return StructuredTool.from_function(
        coroutine=_run,
        name=ag_tool.name,
        description=ag_tool.description or f"AG-UI tool: {ag_tool.name}",
        args_schema=args_schema,
    )


def agui_tools_to_langchain(tools: Sequence[AguiTool]) -> list[StructuredTool]:
    """Convert AG-UI tools from the run request to LangChain structured tools."""
    return [agui_tool_to_langchain(t) for t in tools]
