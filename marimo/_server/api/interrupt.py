# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server import sessions
from marimo._server.api.validated_handler import ValidatedHandler


class InterruptHandler(ValidatedHandler):
    """Interrupt the kernel's execution."""

    @sessions.requires_edit
    def post(self) -> None:
        sessions.require_session_from_header(
            self.request.headers
        ).try_interrupt()
