# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass

from marimo._server import server_utils as sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class Stdin:
    text: str


class StdinHandler(ValidatedHandler):
    """Send input to the stdin stream."""

    @sessions.requires_edit
    def post(self) -> None:
        args = parse_raw(self.request.body, Stdin)
        session = sessions.require_session_from_header(self.request.headers)
        session.input_queue.put(args.text)
