from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from marimo._ai.tools.base import ToolBase


class _Args(BaseModel):
    value: int


class _Out(BaseModel):
    doubled: int


class _EchoTool(ToolBase[_Args, _Out]):
    """Dummy tool for testing base adapter behavior."""

    def __call__(self, args: _Args) -> _Out:
        return _Out(doubled=args.value * 2)


def test_as_mcp_tool_fn_returns_async_callable() -> None:
    tool = _EchoTool(app=None)
    handler = tool.as_mcp_tool_fn()

    assert inspect.iscoroutinefunction(handler)


def test_handler_annotations_and_signature() -> None:
    tool = _EchoTool(app=None)
    handler = tool.as_mcp_tool_fn()

    annotations: dict[str, Any] = getattr(handler, "__annotations__", {})
    assert annotations.get("args") is _Args
    assert annotations.get("return") is _Out

    sig = getattr(handler, "__signature__", None)
    assert sig is not None
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "args"
    assert sig.return_annotation is _Out


def test_name_and_description_defaults() -> None:
    tool = _EchoTool(app=None)
    # Name should default from class name
    assert tool.name == "_echo_tool"
    # Description defaults to class docstring (stripped)
    assert "Dummy tool" in (tool.description or "")
