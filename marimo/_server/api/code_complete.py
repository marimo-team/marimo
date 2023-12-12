# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class CodeComplete:
    id: str
    document: str
    cell_id: CellId_t


class CodeCompleteHandler(ValidatedHandler):
    """Complete a code fragment."""

    @sessions.requires_edit
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
