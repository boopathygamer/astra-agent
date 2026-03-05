"""
MCP Integration — Model Context Protocol server for SuperChain Universal AI Agent.
──────────────────────────────────────────────────────────────────────────────────
Exposes the entire super-system via MCP, enabling any MCP-compatible software
(Claude Desktop, Cursor, VS Code, Windsurf, etc.) to access agent capabilities.

Transports:
  - stdio:  python -m backend.mcp
  - HTTP:   python -m backend.mcp --transport http --port 8080
"""

from mcp.server.fastmcp import FastMCP

from .server import create_mcp_server

__all__ = ["create_mcp_server", "FastMCP"]
