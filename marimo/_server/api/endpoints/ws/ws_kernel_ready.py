# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import (
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._plugins.core.web_component import JSONType
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._server.file_router import MarimoFileKey
    from marimo._server.rtc.doc import LoroDocManager
    from marimo._server.session_manager import SessionManager
    from marimo._session import Session

LOGGER = _loggers.marimo_logger()

LORO_ALLOWED = sys.version_info >= (3, 11)


def build_kernel_ready(
    session: Session,
    manager: SessionManager,
    resumed: bool,
    ui_values: dict[str, JSONType],
    last_executed_code: dict[CellId_t, str],
    last_execution_time: dict[CellId_t, float],
    kiosk: bool,
    rtc_enabled: bool,
    file_key: MarimoFileKey,
    mode: SessionMode,
    doc_manager: LoroDocManager,
    auto_instantiated: bool = False,
) -> KernelReadyNotification:
    """Build a KernelReady message.

    Args:
        session: Current session
        manager: Session manager
        resumed: Whether this is a resumed session
        ui_values: UI element values
        last_executed_code: Last executed code for each cell
        last_execution_time: Last execution time for each cell
        kiosk: Whether this is kiosk mode
        rtc_enabled: Whether RTC is enabled
        file_key: File key for the session
        mode: Session mode (edit/run)
        doc_manager: LoroDoc manager for RTC
        auto_instantiated: Whether the kernel has already been instantiated
            server-side (run mode). If True, the frontend does not need
            to instantiate the app.

    Returns:
        KernelReady message operation.
    """
    codes, names, configs, cell_ids = _extract_cell_data(session, manager)

    # Initialize RTC if needed
    if _should_init_rtc(rtc_enabled, mode):
        _try_init_rtc_doc(cell_ids, codes, file_key, doc_manager)

    return KernelReadyNotification(
        codes=codes,
        names=names,
        configs=configs,
        layout=session.app_file_manager.read_layout_config(),
        cell_ids=cell_ids,
        resumed=resumed,
        ui_values=ui_values,
        last_executed_code=last_executed_code,
        last_execution_time=last_execution_time,
        app_config=session.app_file_manager.app.config,
        kiosk=kiosk,
        capabilities=KernelCapabilitiesNotification(),
        auto_instantiated=auto_instantiated,
    )


def _extract_cell_data(
    session: Session,
    manager: SessionManager,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[CellConfig, ...],
    tuple[CellId_t, ...],
]:
    """Extract cell data based on mode.

    Args:
        session: Current session
        manager: Session manager

    Returns:
        Tuple of (codes, names, configs, cell_ids).
    """
    file_manager = session.app_file_manager
    app = file_manager.app

    if manager.should_send_code_to_frontend():
        # Send full cell data to frontend
        codes, names, configs, cell_ids = tuple(
            zip(
                *tuple(
                    (
                        cell_data.code,
                        cell_data.name,
                        cell_data.config,
                        cell_data.cell_id,
                    )
                    for cell_data in app.cell_manager.cell_data()
                )
            )
        )
        return codes, names, configs, cell_ids
    else:
        # Don't send code to frontend in run mode
        codes, names, configs, cell_ids = tuple(
            zip(
                *tuple(
                    ("", "", cell_data.config, cell_data.cell_id)
                    for cell_data in app.cell_manager.cell_data()
                )
            )
        )
        return codes, names, configs, cell_ids


def is_rtc_available() -> bool:
    """Check if RTC (Loro) is available on this system.

    Returns:
        True if Loro is available, False otherwise.
    """
    return LORO_ALLOWED and DependencyManager.loro.has()


def _should_init_rtc(rtc_enabled: bool, mode: SessionMode) -> bool:
    """Check if RTC should be initialized.

    Args:
        rtc_enabled: Whether RTC is currently enabled
        mode: Session mode (edit/run)

    Returns:
        True if RTC should be initialized, False otherwise.
    """
    return rtc_enabled and mode == SessionMode.EDIT and is_rtc_available()


def _try_init_rtc_doc(
    cell_ids: tuple[CellId_t, ...],
    codes: tuple[str, ...],
    file_key: MarimoFileKey,
    doc_manager: LoroDocManager,
) -> None:
    """Try to initialize RTC document with cell data.

    Logs a warning if Loro is not available but does not fail.

    Args:
        cell_ids: Cell IDs to initialize
        codes: Cell codes to initialize
        file_key: File key for the document
        doc_manager: LoroDoc manager
    """
    if not LORO_ALLOWED:
        LOGGER.warning("RTC: Python version is not supported (requires 3.11+)")
    elif not DependencyManager.loro.has():
        LOGGER.warning(
            "RTC: Loro is not installed, disabling real-time collaboration"
        )
    else:
        asyncio.create_task(doc_manager.create_doc(file_key, cell_ids, codes))
