"""
MCP Server Entry Point — Run via: python -m backend.mcp_server
─────────────────────────────────────────────────────────
Transports:
  stdio (default):  python -m backend.mcp_server
  HTTP:             python -m backend.mcp_server --transport http --port 8080

Environment Variables:
  LLM_PROVIDER       — auto | gemini | claude | chatgpt
  GEMINI_API_KEY     — Google Gemini API key
  CLAUDE_API_KEY     — Anthropic Claude API key
  OPENAI_API_KEY     — OpenAI API key
  MCP_PORT           — HTTP transport port (default: 8080)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure backend is on sys.path
_BACKEND_DIR = str(Path(__file__).parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def main():
    parser = argparse.ArgumentParser(
        description="SuperChain AI Agent — MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.mcp_server                          # stdio transport (Claude Desktop)
  python -m backend.mcp_server --transport http          # HTTP transport on port 8080
  python -m backend.mcp_server --transport http -p 9000  # HTTP on custom port
  python -m backend.mcp_server --verbose                 # Enable debug logging
        """,
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.getenv("MCP_PORT", "8080")),
        help="HTTP transport port (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP transport host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # MCP stdio uses stdout, logs go to stderr
    )

    logger = logging.getLogger("mcp")
    logger.info(f"Starting MCP server — transport={args.transport}")

    # Create server
    from mcp_server.server import create_mcp_server
    server = create_mcp_server()

    # Run with selected transport
    if args.transport == "stdio":
        logger.info("MCP server running on stdio transport")
        server.run(transport="stdio")
    else:
        logger.info(f"MCP server running on http://{args.host}:{args.port}/mcp")
        server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()
