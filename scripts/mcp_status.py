"""Print MCP system + data health JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server import adapters as A

print(json.dumps({"system": A.system_status(), "data_health": A.data_health_snapshot()}, indent=2))
