# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import signal
from typing import Any, Callable, Optional

from marimo import _loggers
from marimo._ast.cell import CellConfig, CellId_t
from marimo._config.config import MarimoConfig
from marimo._messaging.types import KernelMessage
from marimo._pyodide.streams import (
    PyodideStderr,
    PyodideStdin,
    PyodideStdout,
    PyodideStream,
)
from marimo._runtime import handlers, patches, requests
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.input_override import input_override
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.requests import (
    AppMetadata,
    CodeCompletionRequest,
    ControlRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runtime import Kernel
from marimo._runtime.utils.set_ui_element_request_manager import (
    SetUIElementRequestManager,
)
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.model import SessionMode
from marimo._server.models.base import deep_to_camel_case
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
    FileUpdateRequest,
    FileUpdateResponse,
)
from marimo._server.models.models import (
    FormatRequest,
    FormatResponse,
    ReadCodeResponse,
    SaveAppConfigurationRequest,
    SaveNotebookRequest,
)
from marimo._server.session.session_view import SessionView
from marimo._snippets.snippets import read_snippets
from marimo._utils.formatter import DefaultFormatter
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()


class AsyncQueueManager:
    """Manages queues for a session."""

    def __init__(self) -> None:
        # Control messages for the kernel (run, set UI element, set config, etc
        # ) are sent through the control queue
        self.control_queue = asyncio.Queue[requests.ControlRequest]()

        # set UI elements duplicated in another queue so they can be batched
        self.set_ui_element_queue = asyncio.Queue[
            requests.SetUIElementValueRequest
        ]()

        # Code completion requests are sent through a separate queue
        self.completion_queue = asyncio.Queue[requests.CodeCompletionRequest]()

        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue = asyncio.Queue[str](maxsize=1)

    def close_queues(self) -> None:
        # kernel thread cleans up read/write conn and IOloop handler on
        # exit; we don't join the thread because we don't want to block
        self.control_queue.put_nowait(requests.StopRequest())


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
            lambda msg: self.session_view.add_raw_operation(msg[1]),
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
            is_edit_mode=self.mode == SessionMode.EDIT,
            configs=self.app_manager.app.cell_manager.config_map(),
            app_metadata=self.app_metadata,
            user_config=self._initial_user_config,
        )
        await self.kernel_task.start()

    def put_control_request(self, request: requests.ControlRequest) -> None:
        self._queue_manager.control_queue.put_nowait(request)
        if isinstance(request, requests.SetUIElementValueRequest):
            self._queue_manager.set_ui_element_queue.put_nowait(request)

    def put_completion_request(
        self, request: requests.CodeCompletionRequest
    ) -> None:
        self._queue_manager.completion_queue.put_nowait(request)

    def put_input(self, text: str) -> None:
        self._queue_manager.input_queue.put_nowait(text)


class PyodideBridge:
    def __init__(
        self,
        session: PyodideSession,
    ):
        self.session = session
        self.file_system = OSFileSystem()

    def put_control_request(self, request: str) -> None:
        @dataclasses.dataclass
        class Container:
            body: requests.ControlRequest

        parsed = parse_raw({"body": json.loads(request)}, Container).body
        self.session.put_control_request(parsed)

    def put_input(self, text: str) -> None:
        self.session.put_input(text)

    def code_complete(self, request: str) -> None:
        parsed = parse_raw(json.loads(request), requests.CodeCompletionRequest)
        self.session.put_completion_request(parsed)

    def read_code(self) -> str:
        contents: str = self.session.app_manager.read_file()
        response = ReadCodeResponse(contents=contents)
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    async def read_snippets(self) -> str:
        snippets = await read_snippets()
        return json.dumps(deep_to_camel_case(dataclasses.asdict(snippets)))

    def format(self, request: str) -> str:
        parsed = parse_raw(json.loads(request), FormatRequest)
        formatter = DefaultFormatter(line_length=parsed.line_length)

        response = FormatResponse(codes=formatter.format(parsed.codes))
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def save(self, request: str) -> None:
        parsed = parse_raw(json.loads(request), SaveNotebookRequest)
        self.session.app_manager.save(parsed)

    def save_app_config(self, request: str) -> None:
        parsed = parse_raw(json.loads(request), SaveAppConfigurationRequest)
        self.session.app_manager.save_app_config(parsed.config)

    def save_user_config(self, request: str) -> None:
        parsed = parse_raw(json.loads(request), requests.SetUserConfigRequest)
        self.session.put_control_request(parsed)

    def rename_file(self, filename: str) -> None:
        self.session.app_manager.rename(filename)

    def list_files(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileListRequest)
        root = body.path or self.file_system.get_root()
        files = self.file_system.list_files(root)
        response = FileListResponse(files=files, root=root)
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def file_details(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileDetailsRequest)
        response = self.file_system.get_details(body.path)
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def create_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileCreateRequest)
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
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def delete_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileDeleteRequest)
        success = self.file_system.delete_file_or_directory(body.path)
        response = FileDeleteResponse(success=success)
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def move_file_or_directory(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileMoveRequest)
        try:
            info = self.file_system.move_file_or_directory(
                body.path, body.new_path
            )
            response = FileMoveResponse(success=True, info=info)
        except Exception as e:
            response = FileMoveResponse(success=False, message=str(e))
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def update_file(
        self,
        request: str,
    ) -> str:
        body = parse_raw(json.loads(request), FileUpdateRequest)
        try:
            with open(body.path, "w") as file:
                file.write(body.contents)
            response = FileUpdateResponse(success=True)
        except Exception as e:
            response = FileUpdateResponse(success=False, message=str(e))
        return json.dumps(deep_to_camel_case(dataclasses.asdict(response)))

    def export_html(self, request: str) -> str:
        parsed = parse_raw(json.loads(request), ExportAsHTMLRequest)
        html, _filename = Exporter().export_as_html(
            file_manager=self.session.app_manager,
            session_view=self.session.session_view,
            display_config=self.session._initial_user_config["display"],
            request=parsed,
        )
        return json.dumps(html)

    def export_markdown(self, request: str) -> str:
        del request
        md, _filename = Exporter().export_as_md(
            file_manager=self.session.app_manager,
        )
        return json.dumps(md)


def _launch_pyodide_kernel(
    control_queue: asyncio.Queue[ControlRequest],
    set_ui_element_queue: asyncio.Queue[SetUIElementValueRequest],
    completion_queue: asyncio.Queue[CodeCompletionRequest],
    input_queue: asyncio.Queue[str],
    on_message: Callable[[KernelMessage], None],
    is_edit_mode: bool,
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

    # Create communication channels
    stream = PyodideStream(on_message, input_queue)
    stdout = PyodideStdout(stream)
    stderr = PyodideStderr(stream)
    stdin = PyodideStdin(stream) if is_edit_mode else None
    debugger = MarimoPdb(stdout=stdout, stdin=stdin) if is_edit_mode else None

    def _enqueue_control_request(req: ControlRequest) -> None:
        control_queue.put_nowait(req)
        if isinstance(req, SetUIElementValueRequest):
            set_ui_element_queue.put_nowait(req)

    kernel = Kernel(
        cell_configs=configs,
        app_metadata=app_metadata,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        module=patches.patch_main_module(
            file=app_metadata.filename, input_override=input_override
        ),
        enqueue_control_request=_enqueue_control_request,
        debugger_override=debugger,
        user_config=user_config,
    )
    initialize_kernel_context(
        kernel=kernel,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        virtual_files_supported=False,
    )

    if is_edit_mode:
        signal.signal(
            signal.SIGINT, handlers.construct_interrupt_handler(kernel)
        )

    ui_element_request_mgr = SetUIElementRequestManager(set_ui_element_queue)

    async def listen_messages() -> None:
        while True:
            request: ControlRequest | None = await control_queue.get()
            LOGGER.debug("received request %s", request)
            if isinstance(request, requests.SetUIElementValueRequest):
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


class RestartableTask:
    def __init__(self, coro: Callable[[], Any]):
        self.coro = coro
        self.task: Optional[asyncio.Task[Any]] = None
        self.stopped = False

    async def start(self) -> None:
        """Create a task that runs the coro."""
        while True:
            if self.stopped:
                break

            try:
                self.task = asyncio.create_task(self.coro())
                await self.task
            except asyncio.CancelledError:
                pass

    def stop(self) -> None:
        # Stop the task and set the stopped flag
        self.stopped = True
        assert self.task is not None
        self.task.cancel()

    def restart(self) -> None:
        # Cancel the current task, which will cause
        # the while loop to start a new task
        assert self.task is not None
        self.task.cancel()
