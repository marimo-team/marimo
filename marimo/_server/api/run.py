# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class Run:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]


class RunHandler(ValidatedHandler):
    """Run multiple cells (and their descendants).

    Updates cell code in the kernel if needed; registers new cells
    for unseen cell IDs.

    Only allowed in edit mode.
    """

    @sessions.requires_edit
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, Run)
        request = requests.ExecuteMultipleRequest(
            tuple(
                requests.ExecutionRequest(cid, code)
                for cid, code in zip(args.cell_ids, args.codes)
            )
        )
        session.queue.put(request)
