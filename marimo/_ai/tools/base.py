# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    cast,
    get_args,
    get_origin,
)

from pydantic import BaseModel

from marimo._ai.tools.types import ArgsT, GenericMcpHandler, OutT

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from starlette.applications import Starlette


class ToolBase(Generic[ArgsT, OutT], ABC):
    """
    Minimal base class for dual-registered tools.

    Subclasses MUST set:
      - name: str (optional; defaults to class name)
      - description: str (optional; defaults to class docstring)
      - Args: Type[BaseModel]  (pydantic input schema)
      - Output: Type[BaseModel] (pydantic output schema)
      - Args and Output must be set via generics, e.g. ToolBase[ArgsModel, OutputModel]
    """

    # Override in subclass, or rely on fallbacks below
    name: str | None = None
    description: str | None = None
    Args: type[ArgsT]
    Output: type[OutT]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Grab ToolBase[...] type parameters and set Args/Output on the subclass."""
        super().__init_subclass__(**kwargs)

        # Find the ToolBase[...] in the subclass' original bases
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is ToolBase:
                a, o = get_args(base)
                cls.Args = a  # type: ignore[assignment]
                cls.Output = o  # type: ignore[assignment]
                break

        # If not provided via generics and not manually set, fail early
        if not hasattr(cls, "Args") or not hasattr(cls, "Output"):
            raise TypeError(
                f"{cls.__name__} must specify type arguments, e.g. "
                f"class {cls.__name__}(ToolBase[ArgsModel, OutputModel]): ..."
            )

    def __init__(self, app: Optional[Starlette]) -> None:
        self.app = app

        # get name from class name
        if self.name is None:
            self.name = _to_snake_case(self.__class__.__name__)

        # get description from class docstring
        if self.description is None:
            self.description = (self.__class__.__doc__ or "").strip()

        # Fail fast if a tool forgot to use Pydantic models
        if not issubclass(self.Args, BaseModel):
            raise TypeError(
                f"Args must inherit from pydantic.BaseModel; got {self.Args!r}"
            )
        if not issubclass(self.Output, BaseModel):
            raise TypeError(
                f"Output must inherit from pydantic.BaseModel; got {self.Output!r}"
            )

    @abstractmethod
    def __call__(self, args: ArgsT) -> OutT | Awaitable[OutT]:
        """Actual tool function."""
        ...

    async def invoke(self, args: ArgsT) -> OutT:
        """
        Unified runner: calls __call__ and awaits if it returns a coroutine.
        Adapters should always use this.
        """
        result = self.__call__(args)
        if inspect.isawaitable(result):
            return await result  # type: ignore[return-value]
        return result  # type: ignore[return-value]

    # adapters

    def as_mcp_tool_fn(self) -> GenericMcpHandler[ArgsT, OutT]:
        """Return a typed, annotated callable suitable for MCP registration."""
        Args = self.Args
        Output = self.Output

        async def handler(args: ArgsT) -> OutT:  # type: ignore[type-var]
            return await self.invoke(args)

        # name/doc metadata (guard for None types)
        handler_any = cast(Any, handler)
        handler_any.__name__ = self.name or handler_any.__name__
        handler_any.__doc__ = self.description or handler_any.__doc__

        # help static consumers and schema tools
        handler_any.__annotations__ = {"args": Args, "return": Output}

        # Advertise intended signature for mypy/tests
        # Keep in try/except to avoid breaking tool registration
        try:
            handler_any.__signature__ = inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        "args",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=Args,
                    )
                ],
                return_annotation=Output,
            )
        except Exception:
            # Best-effort only; safe to skip if inspect behavior changes
            pass

        return cast(GenericMcpHandler[ArgsT, OutT], handler)

    def as_backend_tool(self) -> None:
        """Convert the tool to a backend tool."""
        # TODO: implement
        ...


# helpers


def _to_snake_case(name: str) -> str:
    """Convert a PascalCase/CamelCase class name to snake_case function name.

    Examples:
        GetCellMap -> get_cell_map
    """
    # Handle acronyms and normal Camel/Pascal case transitions
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.replace("-", "_").lower()
