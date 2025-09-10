import pytest
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._mcp.server.tools.cells import register_cells_tools

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")


def test_register_cells_tools_registers_callables(monkeypatch) -> None:
    app = Starlette()
    mcp = FastMCP("test")

    calls = []

    def recorder():
        def deco(fn):
            calls.append(fn)
            return fn

        return deco

    monkeypatch.setattr(mcp, "tool", recorder)

    register_cells_tools(mcp, app)
    assert len(calls) >= 2
