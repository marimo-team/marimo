# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import tornado.web

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class Run:
    # ids of cells to run
    cell_ids: List[CellId_t]
    # code to register/run for each cell
    codes: List[str]


class RunHandler(tornado.web.RequestHandler):
    """Run multiple cells (and their descendants).

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
