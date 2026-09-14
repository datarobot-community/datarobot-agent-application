# MCP Server Development Instructions

The MCP server MUST be implemented in the `mcp_server/` directory.
By default it provides tools for DataRobot operations, but can be extended with custom tools for any domain.

## MCP Server Development Guidelines

IMPORTANT: Do NOT import code from `agent/` or `fastapi_server/` directories. The MCP server has independent dependencies to avoid conflicts.
IMPORTANT: The MCP server runs as an independent service. Agents connect to it via MCP protocol (HTTP), not direct Python imports.

- You may modify files ONLY inside `mcp_server/` directory.
- The MCP server is a standard FastMCP application:
  * Tools live in `mcp_server/app/tools/`
  * Prompts live in `mcp_server/app/prompts/`
  * Resources live in `mcp_server/app/resources/`
  * Configuration is in `mcp_server/app/core/`
  * Tests are in `mcp_server/app/tests/`
- Read `mcp_server/docs` to further understand the existing structure.

## Tool Development Architecture

The MCP server uses auto-discovery for tools:

1. **Tool Definition** (`mcp_server/app/tools/{domain}_tools.py`): Define tools with `@dr_mcp_tool` decorator
2. **Auto-Discovery**: Server automatically loads all tools from `mcp_server/app/tools/` on startup
3. **MCP Protocol**: Agents discover and call tools via HTTP (no imports needed)

**When adding new tools:**
- Create tool functions in `app/tools/{domain}_tools.py`
- Use `@dr_mcp_tool(tags={"category", "action"})` decorator
- Define parameters with `Annotated[type, "description"]`
- Return `ToolResult(structured_content={...})`
- Tools are automatically discovered - no registration needed

**CRITICAL - Tool Implementation Requirements:**

All tool functions MUST be `async def` and return `ToolResult`. Example:

```python
from typing import Annotated
from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.tools.tool import ToolResult

@dr_mcp_tool(tags={"domain", "action"})
async def tool_name(
    param: Annotated[str, "Parameter description for LLM"],
) -> ToolResult:
    """
    Tool description that the LLM will see.
    Be clear and specific about what the tool does.
    """
    # Your implementation here
    result = {"key": "value"}
    return ToolResult(structured_content=result)
```

## MCP Server Security

- NEVER hardcode API keys or secrets in tool code. Use environment variables or runtime parameters.
- Store credentials in `.env` file (never commit to git)
- Access config via `app/core/user_config.py`
- Use DataRobot credentials management for production deployments

## Installing MCP Server packages

Before making any changes to the mcp_server code, install dependencies by running shell command:

```shell
dr run mcp_server:install
```

## MCP Server Testing

```shell
dr run mcp_server:lint
```

```shell
dr run mcp_server:test
```
