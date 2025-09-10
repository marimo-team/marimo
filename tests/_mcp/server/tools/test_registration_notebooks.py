import pytest
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._mcp.server.tools.notebooks import register_notebooks_tools

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")


def test_register_notebooks_tools_registers_callable(monkeypatch) -> None:
    app = Starlette()
    mcp = FastMCP("test")

    calls = []

    def recorder():
        def deco(fn):
            calls.append(fn)
            return fn

        return deco

    monkeypatch.setattr(mcp, "tool", recorder)

    register_notebooks_tools(mcp, app)
    assert len(calls) >= 1
