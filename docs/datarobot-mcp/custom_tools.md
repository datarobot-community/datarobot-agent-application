# Developing custom tools

### Create a tool

Add custom tools under `mcp_server/app/tools/`.

Example:

```python
# mcp_server/app/tools/my_custom_tool.py
from typing import Annotated

import datarobot as dr
from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult


@dr_mcp_tool(tags={"custom", "example"})
async def my_custom_tool(
    input_param: Annotated[str, "A required input string."],
    optional_param: Annotated[int, "Optional integer parameter."] = 10,
) -> ToolResult:
    """
    Example custom tool.

    Keep the description specific so the LLM can decide when to use the tool.
    """
    if not input_param.strip():
        raise ToolError("input_param cannot be empty.")

    # Example DataRobot API call.
    _ = dr.Project.list()

    return ToolResult(
        structured_content={
            "message": f"Processed {input_param!r} with {optional_param}"
        }
    )
```

### Tool best practices

- Use clear docstrings so the LLM can understand the tool's purpose.
- Add type hints for every parameter and the return value.
- Use `Annotated[...]` to provide short, helpful parameter descriptions.
- Raise `ToolError` for validation failures or expected runtime errors.
- Return structured results when possible so downstream consumers can parse them easily.
- Use descriptive tags to group related tools.

### Work with prompts and resources

The server also loads modules from:

- `mcp_server/app/prompts/`
- `mcp_server/app/resources/`

These directories are already wired into the server in `app/main.py`. Add new modules there if you want to define custom prompts or resources alongside your tools.

### Update the server lifecycle

To add startup or shutdown behavior, edit the existing `ServerLifecycle` class in `mcp_server/app/core/server_lifecycle.py`.

Common uses include:

- opening connections before the server starts
- validating configuration
- starting or stopping background work
- cleaning up resources during shutdown

The generated file already includes these hooks:

- `pre_server_start`
- `post_server_start`
- `pre_server_shutdown`

Add your logic inside those methods instead of replacing the lifecycle class entirely.