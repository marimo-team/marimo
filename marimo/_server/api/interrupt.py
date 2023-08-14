# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import tornado.web

from marimo._server import sessions


class InterruptHandler(tornado.web.RequestHandler):
    """Interrupt the kernel's execution."""

    def post(self) -> None:
        sessions.require_session_from_header(
            self.request.headers
        ).try_interrupt()
