"""
Local Quant Engine — MCP Server (stdio entrypoint).

Delegates to src.mcp_server for all tools. Register in Cursor/Claude via:
  .cursor/mcp.json  or  .mcp.json
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mcp_server.server import create_mcp_app

mcp = create_mcp_app()

if __name__ == "__main__":
    mcp.run()
