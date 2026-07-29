"""Entry point for running MCP server as a module.

Usage:
    python -m novel_ai_writer.backend.mcp
"""
import asyncio
from novel_ai_writer.backend.mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
