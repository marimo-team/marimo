# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from marimo._config.config import merge_config
from marimo._messaging.notification import (
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    ExecuteCellCommand,
    SerializedQueryParams,
    UpdateUIElementCommand,
)
from marimo._server.app_defaults import AppDefaults
from marimo._server.models.models import SaveNotebookRequest
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from marimo._config.config import MarimoConfig
    from marimo._messaging.types import KernelMessage
    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession


def instantiate(
    session: PyodideSession, auto_instantiate: bool = True
) -> None:
    """
    Instantiate the marimo app in the session.

    This function is called by the WebAssembly frontend.
    """

    app = session.app_manager.app
    execution_requests = tuple(
        ExecuteCellCommand(
            cell_id=cell_data.cell_id,
            code=cell_data.code,
            request=None,
        )
        for cell_data in app.cell_manager.cell_data()
    )

    session.put_control_request(
        CreateNotebookCommand(
            execution_requests=execution_requests,
            set_ui_element_value_request=UpdateUIElementCommand(
                object_ids=[], values=[], request=None
            ),
            auto_run=auto_instantiate,
        )
    )


def create_session(
    filename: str,
    query_params: SerializedQueryParams,
    message_callback: Callable[[str], None],
    user_config: MarimoConfig,
) -> tuple[PyodideSession, PyodideBridge]:
    """
    Create a session with the given filename and query parameters.

    Args:
        filename: The filename of the app.
        query_params: The query parameters from the URL.
        message_callback: A callback that can be used to send messages to the
            frontend.
        user_config: The user configuration.

    Returns:
        A tuple of (session, bridge)

    This function is called by the WebAssembly frontend.
    """

    def write_kernel_message(notification: KernelMessage) -> None:
        data_json_str = notification.decode("utf-8")
        name = deserialize_kernel_message(notification).name
        text = f'{{"op": "{name}", "data": {data_json_str}}}'
        message_callback(text)

    # Lazy import to decrease startup time
    from marimo._config.config import merge_default_config
    from marimo._config.manager import ScriptConfigManager

    # Add default config
    user_config = merge_default_config(user_config)
    script_config = ScriptConfigManager(filename).get_config(
        hide_secrets=False
    )
    # Merge with inline script-metadata config
    user_config = merge_config(user_config, script_config)

    app_file_manager = AppFileManager(
        filename=filename,
        defaults=AppDefaults(
            width=user_config["display"]["default_width"],
            sql_output=user_config["runtime"]["default_sql_output"],
        ),
    )
    app = app_file_manager.app

    # We want this message to be performant, so any expensive operations
    # should be after this message is sent
    write_kernel_message(
        serialize_kernel_message(
            KernelReadyNotification(
                codes=tuple(app.cell_manager.codes()),
                names=tuple(app.cell_manager.names()),
                configs=tuple(app.cell_manager.configs()),
                cell_ids=tuple(app.cell_manager.cell_ids()),
                layout=app_file_manager.read_layout_config(),
                resumed=False,
                ui_values={},
                last_executed_code={},
                last_execution_time={},
                app_config=app.config,
                kiosk=False,
                capabilities=KernelCapabilitiesNotification(),
            )
        ),
    )

    from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession

    session = PyodideSession(
        app_file_manager,
        SessionMode.EDIT,
        write_kernel_message,
        AppMetadata(
            query_params=query_params,
            filename=filename,
            cli_args={},
            argv=[],
            app_config=app.config,
        ),
        user_config,
    )

    bridge = PyodideBridge(session)

    return session, bridge


def save_file(
    request: str,
    filename: str,
) -> None:
    """
    Save the app to the given filename.

    Args:
        request: serialized/stringified SaveNotebookRequest
        filename: the filename of the app

    This function is called by the WebAssembly frontend.
    """
    parsed = parse_raw(json.loads(request), SaveNotebookRequest)
    app_file_manager = AppFileManager(filename=filename)
    app_file_manager.save(parsed)
