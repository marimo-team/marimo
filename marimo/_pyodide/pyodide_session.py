# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import base64
import json
import re
import signal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from marimo import _loggers
from marimo._config.config import (
    MarimoConfig,
    PartialMarimoConfig,
    merge_default_config,
)
from marimo._convert.markdown import convert_from_ir_to_markdown
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._pyodide.restartable_task import RestartableTask
from marimo._pyodide.streams import (
    PyodideStderr,
    PyodideStdin,
    PyodideStdout,
    PyodideStream,
)
from marimo._runtime import commands, handlers, patches
from marimo._runtime.commands import (
    AppMetadata,
    CodeCompletionCommand,
    CommandMessage,
    UpdateUIElementCommand,
    UpdateUserConfigCommand,
)
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.input_override import input_override
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from marimo._runtime.utils.set_ui_element_request_manager import (
    SetUIElementRequestManager,
)
from marimo._server.export.exporter import Exporter
from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.models.files import (
    FileCreateRequest,
    FileCreateResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FileDetailsRequest,
    FileListRequest,
    FileListResponse,
    FileMoveRequest,
    FileMoveResponse,
    FileSearchRequest,
    FileSearchResponse,
    FileUpdateRequest,
    FileUpdateResponse,
)
from marimo._server.models.models import (
    FormatCellsRequest,
    FormatResponse,
    ReadCodeResponse,
    SaveAppConfigurationRequest,
    SaveNotebookRequest,
    SaveUserConfigurationRequest,
)
from marimo._session.model import SessionMode
from marimo._session.state.session_view import SessionView
from marimo._snippets.snippets import read_snippets
from marimo._utils.formatter import DefaultFormatter
from marimo._utils.inline_script_metadata import PyProjectReader
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._messaging.types import KernelMessage
    from marimo._session.notebook.file_manager import AppFileManager
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class AsyncQueueManager:
    """Manages queues for a session."""

    def __init__(self) -> None:
        # Control messages for the kernel (run, set UI element, set config, etc
        # ) are sent through the control queue
        self.control_queue = asyncio.Queue[commands.CommandMessage]()

        # set UI elements duplicated in another queue so they can be batched
        self.set_ui_element_queue = asyncio.Queue[
            commands.UpdateUIElementCommand
        ]()

        # Code completion requests are sent through a separate queue
        self.completion_queue = asyncio.Queue[commands.CodeCompletionCommand]()

        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue = asyncio.Queue[str](maxsize=1)

    def close_queues(self) -> None:
        # kernel thread cleans up read/write conn and IOloop handler on
        # exit; we don't join the thread because we don't want to block
        self.control_queue.put_nowait(commands.StopKernelCommand())


class PyodideSession:
    """A client session that is compatible with Pyodide."""

    def __init__(
        self,
        app: AppFileManager,
        mode: SessionMode,
        on_write: Callable[[KernelMessage], None],
        app_metadata: AppMetadata,
        user_config: MarimoConfig,
    ) -> None:
        """Initialize kernel and client connection to it."""
        self.app_manager = app
        self.mode = mode
        self.app_metadata = app_metadata
        self._queue_manager = AsyncQueueManager()
        self.session_consumer = on_write
        self.session_view = SessionView()
        self._initial_user_config = user_config

        self.consumers: list[Callable[[KernelMessage], None]] = [
            lambda msg: self.session_consumer(msg),
            lambda msg: self.session_view.add_raw_notification(msg),
        ]

    def _on_message(self, msg: KernelMessage) -> None:
        for consumer in self.consumers:
            consumer(msg)

    async def start(self) -> None:
        self.kernel_task = _launch_pyodide_kernel(
            control_queue=self._queue_manager.control_queue,
            set_ui_element_queue=self._queue_manager.set_ui_element_queue,
            completion_queue=self._queue_manager.completion_queue,
            input_queue=self._queue_manager.input_queue,
            on_message=self._on_message,
            session_mode=self.mode,
            configs=self.app_manager.app.cell_manager.config_map(),
            app_metadata=self.app_metadata,
            user_config=self._initial_user_config,
        )
        await self.kernel_task.start()

    def put_control_request(self, request: commands.CommandMessage) -> None:
        self._queue_manager.control_queue.put_nowait(request)
        if isinstance(request, commands.UpdateUIElementCommand):
            self._queue_manager.set_ui_element_queue.put_nowait(request)

    def put_completion_request(
        self, request: commands.CodeCompletionCommand
    ) -> None:
        self._queue_manager.completion_queue.put_nowait(request)

    def put_input(self, text: str) -> None:
        self._queue_manager.input_queue.put_nowait(text)

    def find_packages(self, code: str) -> list[str]:
        """
        Find the packages in the code based on the imports,
        and mapping from module names to package names.
        """

        # Prefer dependencies from script metadata
        try:
            reader = PyProjectReader.from_script(code)
            script_deps = reader.dependencies

            def strip_version(dep: str) -> str:
                """
                Strip version specifiers from a dependency string.
                Handles PEP 440 version specifiers, extras, and URLs.
                """
                if not dep or not isinstance(dep, str):
                    return dep if isinstance(dep, str) else ""

                # Strip whitespace
                dep = dep.strip()
                if not dep:
                    return dep

                # Handle URL dependencies (package @ <url>) - leave as-is
                # PEP 508 allows various URL schemes: http, https, git+https, git+ssh, file, ftp, etc.
                if "@" in dep:
                    _, rhs = dep.split("@", 1)
                    rhs = rhs.strip()
                    # Check for URL scheme pattern (e.g., https://, git+https://, file://)
                    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", rhs):
                        return dep

                # Handle environment markers (package>=1.0; python_version>='3.8')
                if ";" in dep:
                    dep = dep.split(";")[0].strip()

                # Split on PEP 440 version specifiers: ==, !=, <=, >=, <, >, ~=, ===
                # Must check multi-char operators first to avoid partial matches
                parts = re.split(
                    r"\s*(?:===|==|!=|<=|>=|~=|<|>)\s*", dep, maxsplit=1
                )

                # Return the package name (first part), preserving extras like 'package[extra]'
                return parts[0].strip() if parts else dep

            if len(script_deps) > 0:
                return [strip_version(dep) for dep in script_deps]
        except Exception as e:
            LOGGER.warning("Error parsing script metadata: %s", e)

        # We don't return "unknown" packages from the imports, since
        # this is used downstream to pre-install packages while loading the notebook
        # without user consent.
        return []


T = TypeVar("T")


def parse_command(request: str) -> commands.CommandMessage:
    """Parse a command string for WASM/Pyodide.

    Args:
        request: JSON string containing the request

    Returns:
        Parsed CommandMessage

    Raises:
        msgspec.DecodeError: If no type successfully parses
    """
    parsed = parse_raw(
        request,
        cls=commands.CommandMessage,  # type: ignore
        allow_unknown_keys=True,
    )
    return cast(commands.CommandMessage, parsed)


class PyodideBridge:
    def __init__(
        self,
        session: PyodideSession,
    ):
        self.session = session
        self.file_system = OSFileSystem()

    def put_control_request(self, request: str) -> None:
        parsed = parse_command(request)
        self.session.put_control_request(parsed)

    def put_input(self, text: str) -> None:
        self.session.put_input(text)

    def code_complete(self, request: str) -> None:
        parsed = self._parse(request, commands.CodeCompletionCommand)
        self.session.put_completion_request(parsed)

    def read_code(self) -> str:
        contents: str = self.session.app_manager.read_file()
        response = ReadCodeResponse(contents=contents)
        return self._dump(response)

    async def read_snippets(self) -> str:
        snippets = await read_snippets(self.session._initial_user_config)
        return self._dump(snippets)

    async def format(self, request: str) -> str:
        parsed = self._parse(request, FormatCellsRequest)
        formatter = DefaultFormatter(line_length=parsed.line_length)

        response = FormatResponse(codes=await formatter.format(parsed.codes))
        return self._dump(response)

    def save(self, request: str) -> None:
        parsed = self._parse(request, SaveNotebookRequest)
        self.session.app_manager.save(parsed)

    def save_app_config(self, request: str) -> None:
        parsed = self._parse(request, SaveAppConfigurationRequest)
        self.session.app_manager.save_app_config(parsed.config)

    def save_user_config(self, request: str) -> None:
        parsed = self._parse(request, SaveUserConfigurationRequest)
        config = merge_default_config(cast(PartialMarimoConfig, parsed.config))
        self.session.put_control_request(
            UpdateUserConfigCommand(config=config)
        )

    def rename_file(self, filename: str) -> None:
        self.session.app_manager.rename(filename)

    def list_files(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileListRequest)
        root = body.path or self.file_system.get_root()
        files = self.file_system.list_files(root)
        response = FileListResponse(files=files, root=root)
        return self._dump(response)

    def search_files(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileSearchRequest)
        files = self.file_system.search(
            query=body.query,
            path=body.path,
            depth=body.depth,
            include_directories=body.include_directories,
            include_files=body.include_files,
            limit=body.limit,
        )
        response = FileSearchResponse(
            files=files, query=body.query, total_found=len(files)
        )
        return self._dump(response)

    def file_details(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileDetailsRequest)
        response = self.file_system.get_details(body.path)
        return self._dump(response)

    def create_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileCreateRequest)
        try:
            # If we need to eliminate the overhead associated with
            # base64-encoding/decoding the file contents, we could try pushing
            # filesystem operations into JavaScript
            decoded_contents = (
                base64.b64decode(body.contents)
                if body.contents is not None
                else None
            )
            info = self.file_system.create_file_or_directory(
                body.path, body.type, body.name, decoded_contents
            )
            response = FileCreateResponse(success=True, info=info)
        except Exception as e:
            response = FileCreateResponse(success=False, message=str(e))
        return self._dump(response)

    def delete_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileDeleteRequest)
        success = self.file_system.delete_file_or_directory(body.path)
        response = FileDeleteResponse(success=success)
        return self._dump(response)

    def move_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileMoveRequest)
        try:
            info = self.file_system.move_file_or_directory(
                body.path, body.new_path
            )
            response = FileMoveResponse(success=True, info=info)
        except Exception as e:
            response = FileMoveResponse(success=False, message=str(e))
        return self._dump(response)

    def update_file(
        self,
        request: str,
    ) -> str:
        body = self._parse(request, FileUpdateRequest)
        try:
            Path(body.path).write_text(body.contents, encoding="utf-8")
            response = FileUpdateResponse(success=True)
        except Exception as e:
            response = FileUpdateResponse(success=False, message=str(e))
        return self._dump(response)

    def export_html(self, request: str) -> str:
        parsed = self._parse(request, ExportAsHTMLRequest)
        html, _filename = Exporter().export_as_html(
            app=self.session.app_manager.app,
            filename=self.session.app_manager.filename,
            session_view=self.session.session_view,
            display_config=self.session._initial_user_config["display"],
            request=parsed,
        )
        return json.dumps(html)

    def export_markdown(self, request: str) -> str:
        del request
        md = convert_from_ir_to_markdown(self.session.app_manager.app.to_ir())
        return json.dumps(md)

    def _parse(self, request: str, cls: type[T]) -> T:
        return parse_raw(request, cls)

    def _dump(self, response: Any) -> str:
        return encode_json_str(response)


def _launch_pyodide_kernel(
    control_queue: asyncio.Queue[CommandMessage],
    set_ui_element_queue: asyncio.Queue[UpdateUIElementCommand],
    completion_queue: asyncio.Queue[CodeCompletionCommand],
    input_queue: asyncio.Queue[str],
    on_message: Callable[[KernelMessage], None],
    session_mode: SessionMode,
    configs: dict[CellId_t, CellConfig],
    app_metadata: AppMetadata,
    user_config: MarimoConfig,
) -> RestartableTask:
    from marimo._output.formatters.formatters import register_formatters

    register_formatters()

    LOGGER.debug("Launching kernel")

    # Patches for pyodide compatibility
    patches.patch_pyodide_networking()

    # Some libraries mess with Python's default recursion limit, which becomes
    # a problem when running with Pyodide.
    patches.patch_recursion_limit(limit=1000)

    is_edit_mode = session_mode == SessionMode.EDIT

    # Create communication channels
    stream = PyodideStream(on_message, input_queue)
    stdout = PyodideStdout(stream)
    stderr = PyodideStderr(stream)
    stdin = PyodideStdin(stream) if is_edit_mode else None
    debugger = MarimoPdb(stdout=stdout, stdin=stdin) if is_edit_mode else None

    def _enqueue_control_request(req: CommandMessage) -> None:
        control_queue.put_nowait(req)
        if isinstance(req, UpdateUIElementCommand):
            set_ui_element_queue.put_nowait(req)

    kernel = Kernel(
        cell_configs=configs,
        app_metadata=app_metadata,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        module=patches.patch_main_module(
            file=app_metadata.filename,
            input_override=input_override,
            print_override=None,
        ),
        enqueue_control_request=_enqueue_control_request,
        debugger_override=debugger,
        user_config=user_config,
    )
    ctx = initialize_kernel_context(
        kernel=kernel,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        virtual_files_supported=False,
        mode=session_mode,
    )

    if is_edit_mode:
        signal.signal(signal.SIGINT, handlers.construct_interrupt_handler(ctx))

    ui_element_request_mgr = SetUIElementRequestManager(set_ui_element_queue)

    async def listen_messages() -> None:
        while True:
            request: CommandMessage | None = await control_queue.get()
            LOGGER.debug("received request %s", request)
            if isinstance(request, commands.UpdateUIElementCommand):
                request = ui_element_request_mgr.process_request(request)

            if request is not None:
                await kernel.handle_message(request)

    async def listen_completion() -> None:
        while True:
            request = await completion_queue.get()
            while not completion_queue.empty():
                # discard stale requests to avoid choking the runtime
                request = await completion_queue.get()
            LOGGER.debug("received completion request %s", request)
            # 5 is arbitrary, but is a good limit:
            # too high will cause long load times
            # too low can be not as useful
            kernel.code_completion(request, docstrings_limit=5)

    async def listen() -> None:
        await asyncio.gather(listen_messages(), listen_completion())

    return RestartableTask(listen)
