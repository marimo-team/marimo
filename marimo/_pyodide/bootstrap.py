# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from marimo._messaging.ops import KernelReady, serialize
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecutionRequest,
    SerializedQueryParams,
    SetUIElementValueRequest,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.model import SessionMode
from marimo._server.models.models import SaveRequest
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig
    from marimo._messaging.types import KernelMessage
    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession


def instantiate(session: PyodideSession) -> None:
    app = session.app_manager.app
    execution_requests = tuple(
        ExecutionRequest(cell_id=cell_data.cell_id, code=cell_data.code)
        for cell_data in app.cell_manager.cell_data()
    )

    session.put_control_request(
        CreationRequest(
            execution_requests=execution_requests,
            set_ui_element_value_request=SetUIElementValueRequest(list()),
        )
    )


def create_session(
    filename: str,
    query_params: SerializedQueryParams,
    message_callback: Callable[[str], None],
    user_config: MarimoConfig,
) -> tuple[PyodideSession, PyodideBridge]:
    def write_kernel_message(op: KernelMessage) -> None:
        message_callback(json.dumps({"op": op[0], "data": op[1]}))

    app_file_manager = AppFileManager(filename=filename)
    app = app_file_manager.app

    # We want this message to be performant, so any expensive operations
    # should be after this message is sent
    write_kernel_message(
        (
            KernelReady.name,
            serialize(
                KernelReady(
                    codes=tuple(app.cell_manager.codes()),
                    names=tuple(app.cell_manager.names()),
                    configs=tuple(app.cell_manager.configs()),
                    cell_ids=tuple(app.cell_manager.cell_ids()),
                    layout=None,
                    resumed=False,
                    ui_values={},
                    last_executed_code={},
                    app_config=app.config,
                )
            ),
        )
    )

    # Lazy import to increase startup time
    from marimo._config.config import merge_default_config
    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession

    session = PyodideSession(
        app_file_manager,
        SessionMode.EDIT,
        write_kernel_message,
        AppMetadata(query_params=query_params, filename=filename, cli_args={}),
        merge_default_config(user_config),
    )

    bridge = PyodideBridge(session)

    return session, bridge


def save_file(
    request: str,
    filename: str,
) -> None:
    parsed = parse_raw(json.loads(request), SaveRequest)
    app_file_manager = AppFileManager(filename=filename)
    app_file_manager.save(parsed)
