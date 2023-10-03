# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any, Dict

import tornado.web

from marimo import _loggers
from marimo._ast import codegen
from marimo._server import sessions
from marimo._server.api.model import parse_raw
from marimo._server.api.status import HTTPStatus

LOGGER = _loggers.marimo_logger()


class VirtualFileHandler(tornado.web.RequestHandler):
    """Handler for virtual files."""

    @sessions.requires_edit
    def get(self, filename) -> None:
        mgr = sessions.get_manager()
        session_id = self.get_argument("session_id")
        if session_id is not None:
            raise tornado.web.HTTPError(
                HTTPStatus.BAD_REQUEST,
                reason="Session ID must be provided",
            )
        if filename is None:
            raise tornado.web.HTTPError(
                HTTPStatus.BAD_REQUEST,
                reason="Filename must be provided",
            )
        session = mgr.get_session(session_id)
        if session is None:
            raise tornado.web.HTTPError(
                HTTPStatus.NOT_FOUND,
                reason="Session not found",
            )

        try:
            buffer_contents = bytes(
                shared_memory.SharedMemory(name=self.request.path).buf
            )
        except FileNotFoundError:
            raise tornado.web.HTTPError(
                HTTPStatus.NOT_FOUND,
                reason="File not found",
            )

        # TODO(akshayka): can we encode mime-type in the path?
        # self.set_header("Content-Type", virtual_file.mimetype)
        self.write(buffer_contents)
