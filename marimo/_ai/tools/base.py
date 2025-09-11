# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

from starlette.applications import (
    Starlette,  # noqa: TCH002 - required at runtime for MCP/Pydantic schema validation and isinstance checks
)

from marimo._ai.tools.utils.exceptions import ToolExecutionError
from marimo._server.api.deps import AppStateBase
from marimo._server.sessions import Session, SessionManager
from marimo._types.ids import SessionId

ArgsT = TypeVar("ArgsT")
OutT = TypeVar("OutT")

ArgsP = TypeVar("ArgsP", contravariant=True)
OutC = TypeVar("OutC", covariant=True)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass
class ToolContext:
    app: Optional[Starlette] = None

    @property
    def session_manager(self) -> SessionManager:
        app = self.get_app()
        state = AppStateBase.from_app(app)
        session_manager = state.session_manager
        return session_manager

    def get_app(self) -> Starlette:
        app = self.app
        if app is None:
            raise ToolExecutionError(
                "App is not available",
                code="APP_NOT_AVAILABLE",
                is_retryable=False,
                suggested_fix="Try restarting the marimo server.",
            )
        return app

    def get_session(self, session_id: SessionId) -> Session:
        session_manager = self.session_manager
        if session_id not in session_manager.sessions:
            raise ToolExecutionError(
                f"Session {session_id} not found",
                code="SESSION_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Use get_active_notebooks to find valid session IDs",
                meta={"session_id": session_id},
            )
        return session_manager.sessions[session_id]


class ToolBase(Generic[ArgsT, OutT], ABC):
    """
    Minimal base class for dual-registered tools.

    Subclasses MUST set:
      - name: str (optional; defaults to class name)
      - description: str (optional; defaults to class docstring)
      - Args: Type (input schema type)
      - Output: Type (output schema type)
      - Args and Output must be set via generics, e.g. ToolBase[ArgsModel, OutputModel]
    """

    # Override in subclass, or rely on fallbacks below
    name: str | None = None
    description: str | None = None
    Args: type[ArgsT]
    Output: type[OutT]
    context: ToolContext

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

    def __init__(self, context: ToolContext) -> None:
        self.context = context

        # get name from class name
        if self.name is None:
            self.name = self._to_snake_case(self.__class__.__name__)

        # get description from class docstring
        if self.description is None:
            self.description = (self.__class__.__doc__ or "").strip()

    async def __call__(self, args: ArgsT) -> OutT:
        """
        Unified runner: calls __call__ and awaits if it returns a coroutine.
        Adapters should always use this.
        """
        coerced_args = self._coerce_args(args)
        try:
            result = self.handle(coerced_args)
            if inspect.isawaitable(result):
                awaited = await result  # type: ignore[no-any-return]
                return cast(OutT, awaited)
            return cast(OutT, result)  # type: ignore[redundant-cast]
        except ToolExecutionError:
            # Let intentional tool errors propagate unchanged
            raise
        except Exception as e:
            # Standardize unexpected failures
            raise ToolExecutionError(
                self._default_error_message(),
                code=self._default_error_code(),
                is_retryable=self._default_is_retryable(),
                suggested_fix=self._default_suggested_fix(),
                meta=self._error_context(coerced_args),
            ) from e

    @abstractmethod
    def handle(self, args: ArgsT) -> OutT:
        """Actual tool function."""
        ...

    # adapters
    def as_mcp_tool_fn(self) -> Callable[[ArgsT], Awaitable[OutT]]:
        """Return a typed, annotated callable suitable for MCP registration."""
        Args = self.Args
        Output = self.Output

        async def handler(args: ArgsT) -> OutT:  # type: ignore[type-var]
            result = await self.__call__(args)
            # Ensure JSON-serializable output for MCP
            if is_dataclass(result):
                # Some MCP clients expect dicts only
                return cast(OutT, asdict(result))  # type: ignore[arg-type]
            return result

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

        return handler

    def as_backend_tool(self) -> None:
        """Convert the tool to a backend tool."""
        # TODO: implement
        ...

    # helpers

    def _coerce_args(self, args: Any) -> ArgsT:  # type: ignore[override]
        """If Args is a dataclass and args is a dict, construct it; else pass through."""
        ArgsType: Any = getattr(self, "Args", None)
        if (
            isinstance(args, dict)
            and inspect.isclass(ArgsType)
            and is_dataclass(ArgsType)
        ):
            try:
                return cast(ArgsT, ArgsType(**args))
            except Exception:
                return cast(ArgsT, args)
        return cast(ArgsT, args)

    def _to_snake_case(self, name: str) -> str:
        """Convert a PascalCase/CamelCase class name to snake_case function name.

        Examples:
            GetCellMap -> get_cell_map
        """
        # Handle acronyms and normal Camel/Pascal case transitions
        s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.replace("-", "_").lower()

    # error defaults/hooks
    def _default_error_code(self) -> str:
        return "UNEXPECTED_ERROR"

    def _default_error_message(self) -> str:
        return f"{self.name or self.__class__.__name__} failed"

    def _default_is_retryable(self) -> bool:
        return True

    def _default_suggested_fix(self) -> Optional[str]:
        return None

    def _error_context(self, _args: Any) -> dict[str, Any]:
        return {}
