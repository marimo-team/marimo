# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

import tornado.web

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class CodeComplete:
    id: str
    document: str
    cell_id: CellId_t


class CodeCompleteHandler(tornado.web.RequestHandler):
    """Complete a path to subdirectories and Python files."""

    def post(self) -> None:
        args = parse_raw(self.request.body, CodeComplete)
        session = sessions.require_session_from_header(self.request.headers)
        session.queue.put(
            requests.CompletionRequest(
                completion_id=args.id,
                document=args.document,
                cell_id=args.cell_id,
            )
        )
