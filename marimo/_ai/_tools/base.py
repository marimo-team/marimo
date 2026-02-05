# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    TypeVar,
    cast,
    get_args,
    get_origin,
)

from marimo import _loggers
from marimo._ai._tools.types import (
    MarimoCellConsoleOutputs,
    MarimoCellErrors,
    MarimoErrorDetail,
    MarimoNotebookInfo,
    ToolGuidelines,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._ai._tools.utils.output_cleaning import clean_output
from marimo._config.config import CopilotMode
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import CellNotification
from marimo._server.ai.tools.types import (
    FunctionArgs,
    ToolDefinition,
    ValidationFunction,
)
from marimo._server.api.deps import AppStateBase
from marimo._session.model import ConnectionState
from marimo._types.ids import CellId_t, SessionId
from marimo._utils.case import to_snake_case
from marimo._utils.dataclass_to_openapi import PythonTypeToOpenAPI
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()

ArgsT = TypeVar("ArgsT")
OutT = TypeVar("OutT")

ArgsP = TypeVar("ArgsP", contravariant=True)
OutC = TypeVar("OutC", covariant=True)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from starlette.applications import Starlette

    from marimo._server.session_manager import SessionManager
    from marimo._session import Session


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
        session = self.session_manager.get_session(session_id)
        if session is None:
            raise ToolExecutionError(
                f"Session {session_id} not found",
                code="SESSION_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Use get_active_notebooks to find valid session IDs",
                meta={"session_id": session_id},
            )
        return session

    def get_cell_notification(
        self, session_id: SessionId, cell_id: CellId_t
    ) -> CellNotification:
        session_view = self.get_session(session_id).session_view
        if cell_id not in session_view.cell_notifications:
            raise ToolExecutionError(
                f"Cell notification not found for cell {cell_id}",
                code="CELL_NOTIFICATION_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Try again with a valid cell ID.",
                meta={"cell_id": cell_id},
            )
        return session_view.cell_notifications[cell_id]

    def get_active_sessions_internal(self) -> list[MarimoNotebookInfo]:
        """
        Get active sessions from the app state.

        This follows the logic from marimo/_server/api/endpoints/home.py
        """
        import os

        UNSAVED_NOTEBOOK_MESSAGE = (
            "(unsaved notebook - save to disk to get file path)"
        )
        files: list[MarimoNotebookInfo] = []
        for session_id, session in self.session_manager.sessions.items():
            state = session.connection_state()
            if (
                state == ConnectionState.OPEN
                or state == ConnectionState.ORPHANED
            ):
                full_file_path = session.app_file_manager.path
                filename = session.app_file_manager.filename
                basename = os.path.basename(filename) if filename else None
                files.append(
                    MarimoNotebookInfo(
                        name=(basename or "new notebook"),
                        # file path should be absolute path for agent-based edit tools
                        path=(full_file_path or UNSAVED_NOTEBOOK_MESSAGE),
                        session_id=session_id,
                    )
                )
        # Return most recent notebooks first (reverse chronological order)
        return files[::-1]

    def get_notebook_errors(
        self, session_id: SessionId, include_stderr: bool
    ) -> list[MarimoCellErrors]:
        """
        Get all errors in the current notebook session, organized by cell.

        Optionally include stderr messages foreach cell.
        """
        session = self.get_session(session_id)
        session_view = session.session_view
        cell_errors_map: dict[CellId_t, MarimoCellErrors] = {}
        notebook_errors: list[MarimoCellErrors] = []
        stderr: list[str] = []

        for cell_id, cell_notif in session_view.cell_notifications.items():
            errors = self.get_cell_errors(
                session_id,
                cell_id,
                maybe_cell_notif=cell_notif,
            )
            if include_stderr:
                stderr = self.get_cell_console_outputs(cell_notif).stderr
            if errors:
                cell_errors_map[cell_id] = MarimoCellErrors(
                    cell_id=cell_id,
                    errors=errors,
                    stderr=stderr,
                )

        # Use cell_manager to get cells in the correct notebook order
        cell_manager = session.app_file_manager.app.cell_manager
        for cell_data in cell_manager.cell_data():
            cell_id = cell_data.cell_id
            if cell_id in cell_errors_map:
                notebook_errors.append(cell_errors_map[cell_id])

        return notebook_errors

    def get_cell_errors(
        self,
        session_id: SessionId,
        cell_id: CellId_t,
        maybe_cell_notif: Optional[CellNotification] = None,
    ) -> list[MarimoErrorDetail]:
        """
        Get all errors for a given cell.
        """
        errors: list[MarimoErrorDetail] = []
        cell_notif = maybe_cell_notif or self.get_cell_notification(
            session_id, cell_id
        )

        if (
            not cell_notif.output
            or cell_notif.output.channel != CellChannel.MARIMO_ERROR
        ):
            return errors

        items = cell_notif.output.data

        if not isinstance(items, list):
            # no errors
            return errors

        for err in items:
            # TODO: filter out noisy useless errors
            # like "An ancestor raised an exception..."
            if isinstance(err, dict):
                errors.append(
                    MarimoErrorDetail(
                        type=err.get("type", "UnknownError"),
                        message=err.get("msg", str(err)),
                        traceback=err.get("traceback", []),
                    )
                )
            else:
                # Fallback for rich error objects
                err_type: str = getattr(err, "type", type(err).__name__)
                describe_fn: Optional[Any] = getattr(err, "describe", None)
                message_val = (
                    describe_fn() if callable(describe_fn) else str(err)
                )
                message: str = str(message_val)
                tb: list[str] = getattr(err, "traceback", []) or []
                errors.append(
                    MarimoErrorDetail(
                        type=err_type,
                        message=message,
                        traceback=tb,
                    )
                )

        return errors

    def get_cell_console_outputs(
        self, cell_notif: CellNotification
    ) -> MarimoCellConsoleOutputs:
        """
        Get the console outputs for a given cell notification.
        """
        stdout_messages: list[str] = []
        stderr_messages: list[str] = []

        if cell_notif.console is None:
            return MarimoCellConsoleOutputs(stdout=[], stderr=[])

        console_outputs = (
            cell_notif.console
            if isinstance(cell_notif.console, list)
            else [cell_notif.console]
        )
        for output in console_outputs:
            if output is None:
                continue
            elif output.channel == CellChannel.STDOUT:
                stdout_messages.append(str(output.data))
            elif output.channel == CellChannel.STDERR:
                stderr_messages.append(str(output.data))

        cleaned_stdout_messages = clean_output(stdout_messages)
        cleaned_stderr_messages = clean_output(stderr_messages)

        return MarimoCellConsoleOutputs(
            stdout=cleaned_stdout_messages, stderr=cleaned_stderr_messages
        )


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
    name: str = ""
    description: str = ""
    guidelines: Optional[ToolGuidelines] = None
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
        if self.name == "":
            self.name = to_snake_case(self.__class__.__name__)

        # get description from class docstring
        if self.description == "":
            base_description = (self.__class__.__doc__ or "").strip()

            # If guidelines exist, append them
            if self.guidelines is not None:
                self.description = self._format_with_guidelines(
                    base_description, self.guidelines
                )
            else:
                self.description = base_description

    async def __call__(self, args: ArgsT) -> OutT:
        """
        Unified runner: calls __call__ and awaits if it returns a coroutine.
        Adapters should always use this.
        """
        try:
            coerced_args = self._coerce_args(args)
        except Exception as e:
            raise ToolExecutionError(
                f"Bad arguments: {args}",
                code="BAD_ARGUMENTS",
                is_retryable=False,
                suggested_fix="Try again with valid arguments.",
                meta={"args": args},
            ) from e
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
            LOGGER.error(f"Unexpected error in tool {self.name}: {e}")
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

    def as_backend_tool(
        self, mode: list[CopilotMode]
    ) -> tuple[ToolDefinition, ValidationFunction]:
        """Convert the tool to a ToolDefinition for backend use."""

        # convert the args to python dict
        converter = PythonTypeToOpenAPI(name_overrides={}, camel_case=False)
        converted_args = converter.convert(self.Args, processed_classes={})

        # get tool_definition
        tool_definition = ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=converted_args,
            source="backend",
            mode=mode,
        )

        # get validation_function
        validation_function = self._create_validation_function(self.Args)

        return tool_definition, validation_function

    # helpers
    def _coerce_args(self, args: Any) -> ArgsT:  # type: ignore[override]
        """If Args is a dataclass and args is a dict, construct it; else pass through."""
        if is_dataclass(args):
            # Already parsed
            return args  # type: ignore[return-value]
        return parse_raw(args, self.Args)

    def _format_with_guidelines(
        self, description: str, guidelines: ToolGuidelines
    ) -> str:
        """Combine description with structured guidelines."""
        parts = [description] if description else []

        if guidelines.when_to_use:
            parts.append("\n## When to use:")
            parts.extend(f"- {item}" for item in guidelines.when_to_use)

        if guidelines.avoid_if:
            parts.append("\n## Avoid if:")
            parts.extend(f"- {item}" for item in guidelines.avoid_if)

        if guidelines.prerequisites:
            parts.append("\n## Prerequisites:")
            parts.extend(f"- {item}" for item in guidelines.prerequisites)

        if guidelines.side_effects:
            parts.append("\n## Side effects:")
            parts.extend(f"- {item}" for item in guidelines.side_effects)

        if guidelines.additional_info:
            parts.append("\n## Additional info:")
            parts.append(guidelines.additional_info)

        return "\n".join(parts)

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

    def _create_validation_function(
        self, args_type: type[Any]
    ) -> ValidationFunction:
        """Create a validator using parse_raw against the tool's Args type."""

        def validation_function(
            arguments: FunctionArgs,
        ) -> Optional[tuple[bool, str]]:
            try:
                # Will raise on bad types/required fields
                parse_raw(arguments, args_type)
                return True, ""
            except Exception as e:
                return False, f"Invalid arguments: {e}"

        return validation_function
