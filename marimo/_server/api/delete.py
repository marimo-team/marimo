# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class Delete:
    cell_id: CellId_t


class DeleteHandler(ValidatedHandler):
    """Delete a cell with a given id"""

    @sessions.requires_edit
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, Delete)
        cell_id = CellId_t(args.cell_id)
        request = requests.DeleteRequest(cell_id=cell_id)
        session.queue.put(request)
