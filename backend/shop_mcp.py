"""The one and only path from the backend to shop data: the campus-customs MCP server.

- SHOP_TOOLSET is a pydantic-ai MCPToolset launched from .mcp.json. Each agent
  gets a filtered view of it containing only its role's tools.
- HUMAN_ONLY_TOOLS are never shown to any agent. The backend calls them through
  call_human_tool() when a person clicks approve/reject on the dashboard.
"""

import json
from typing import Any

from fastmcp import Client
from pydantic_ai.mcp import MCPToolset

from backend.config import MCP_CONFIG_PATH, MCP_SERVER_NAME, PROJECT_DIR

HUMAN_ONLY_TOOLS = frozenset({"approve_and_pay", "reject_approval"})


def _mcp_config() -> dict:
    config = json.loads(MCP_CONFIG_PATH.read_text())
    if MCP_SERVER_NAME not in config.get("mcpServers", {}):
        raise RuntimeError(f"{MCP_CONFIG_PATH} has no '{MCP_SERVER_NAME}' server.")
    server = dict(config["mcpServers"][MCP_SERVER_NAME])
    # .mcp.json uses project-relative paths; resolve them so the backend works from any cwd (e.g. backend/).
    def resolve(value: str) -> str:
        path = PROJECT_DIR / value
        return str(path) if not value.startswith("/") and ("/" in value or path.exists()) else value
    server["command"] = resolve(server["command"])
    server["args"] = [resolve(a) for a in server.get("args", [])]
    server["env"] = {k: resolve(v) for k, v in server.get("env", {}).items()}
    server["cwd"] = str(PROJECT_DIR)
    return {"mcpServers": {MCP_SERVER_NAME: server}}


SHOP_TOOLSET = MCPToolset(Client(_mcp_config()), id=MCP_SERVER_NAME)


def toolset_for(allowed: frozenset[str]):
    """A view of the MCP server limited to `allowed` (minus human-only tools)."""
    visible = allowed - HUMAN_ONLY_TOOLS
    return SHOP_TOOLSET.filtered(lambda ctx, tool_def: tool_def.name in visible)


async def list_server_tools() -> list[str]:
    async with Client(_mcp_config()) as client:
        return [t.name for t in await client.list_tools()]


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call any MCP tool directly (used by the API for read-only board views)."""
    async with Client(_mcp_config()) as client:
        result = await client.call_tool(name, arguments or {}, raise_on_error=False)
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    return data


async def call_human_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Call a human-only tool. Only the approval endpoint should use this."""
    if name not in HUMAN_ONLY_TOOLS:
        raise ValueError(f"{name} is not a human-only tool.")
    return await call_tool(name, arguments)
