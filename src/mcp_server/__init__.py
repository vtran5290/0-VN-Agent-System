"""MCP orchestration layer — compact JSON tools over existing repo logic."""

__all__ = ["create_mcp_app"]


def create_mcp_app():
    from src.mcp_server.server import create_mcp_app as _create

    return _create()
