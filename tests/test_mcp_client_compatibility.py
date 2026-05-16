"""Cursor + Claude Code MCP config compatibility.

Verifies both clients point at the same `scripts/mcp_quant_engine.py`
entrypoint with identical server name, and that example files match.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

CURSOR_CFG = REPO / ".cursor/mcp.json"
CLAUDE_CFG = REPO / ".mcp.json"
CURSOR_EX = REPO / "config/mcp/cursor_mcp_config.example.json"
CLAUDE_EX = REPO / "config/mcp/claude_code_mcp_config.example.json"

CFG_FILES = [CURSOR_CFG, CLAUDE_CFG, CURSOR_EX, CLAUDE_EX]


@pytest.mark.parametrize("path", CFG_FILES, ids=[p.name for p in CFG_FILES])
def test_config_exists(path: Path):
    assert path.exists(), f"missing MCP config: {path}"


@pytest.mark.parametrize("path", CFG_FILES, ids=[p.name for p in CFG_FILES])
def test_config_has_local_quant_engine(path: Path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert "mcpServers" in cfg
    assert "local-quant-engine" in cfg["mcpServers"]


@pytest.mark.parametrize("path", CFG_FILES, ids=[p.name for p in CFG_FILES])
def test_entrypoint_is_mcp_quant_engine(path: Path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    args = cfg["mcpServers"]["local-quant-engine"]["args"]
    assert any(a.endswith("mcp_quant_engine.py") for a in args), args


def test_cursor_and_claude_use_same_script_filename():
    cur = json.loads(CURSOR_CFG.read_text(encoding="utf-8"))
    cla = json.loads(CLAUDE_CFG.read_text(encoding="utf-8"))
    cur_arg = next(a for a in cur["mcpServers"]["local-quant-engine"]["args"] if a.endswith(".py"))
    cla_arg = next(a for a in cla["mcpServers"]["local-quant-engine"]["args"] if a.endswith(".py"))
    assert Path(cur_arg).name == Path(cla_arg).name == "mcp_quant_engine.py"


@pytest.mark.parametrize("path", CFG_FILES, ids=[p.name for p in CFG_FILES])
def test_no_hardcoded_personal_paths(path: Path):
    text = path.read_text(encoding="utf-8")
    forbidden = ["C:\\\\Users\\\\LOLII", "c:\\\\Users\\\\LOLII", "C:/Users/LOLII", "c:/Users/LOLII"]
    for f in forbidden:
        assert f not in text, f"{path.name} contains personal path fragment {f!r}"


@pytest.mark.parametrize("path", CFG_FILES, ids=[p.name for p in CFG_FILES])
def test_no_inline_secrets(path: Path):
    """API keys / tokens must not be inlined in JSON; use envFile / ${env:...}."""
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for server, spec in cfg["mcpServers"].items():
        env = spec.get("env", {}) or {}
        for k, v in env.items():
            if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                assert not v or "${" in str(v), f"{server}.{k} looks like inline secret: {v!r}"
