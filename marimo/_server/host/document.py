# Copyright 2026 Marimo. All rights reserved.
"""Translate between host records and the editor's document model.

The host owns protocol edits and etags. Sessions still own the editor's
transaction history, so the bridge mirrors each session transaction into
the host document.

While a session is attached it also owns the app config, and the host
document only mirrors it. Host edits change cells and their order.

TODO: An editor app config change produces no document transaction, so
the host does not learn of it until the next cell transaction, and
`app_config` and `app_config_etag` on the host stream lag until then.
Nothing writes app config from the host side, so no data is at risk.
Resolve once the frontend consumes the host protocol, when a config
change becomes a change on the core document like any other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._core import protocol
from marimo._core.document import CellSource

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session


def from_session(session: Session) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(cell.id, cell.code, cell.name, _config(cell.config))
        for cell in session.document.cells
    ]
    return cells, session.app_file_manager.app.config.asdict_difference()


def from_file_manager(
    manager: AppFileManager,
) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(data.cell_id, data.code, data.name, _config(data.config))
        for data in manager.app.cell_manager.cell_data()
    ]
    return cells, manager.app.config.asdict_difference()


def _config(config: CellConfig) -> protocol.CellConfig:
    return protocol.CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )
