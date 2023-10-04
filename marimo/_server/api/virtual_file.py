# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from multiprocessing import shared_memory

import tornado.web

from marimo import _loggers
from marimo._server.api.status import HTTPStatus

LOGGER = _loggers.marimo_logger()


class VirtualFileHandler(tornado.web.RequestHandler):
    """Handler for virtual files."""

    def get(self, filename) -> None:
        if filename is None:
            raise tornado.web.HTTPError(
                HTTPStatus.BAD_REQUEST,
                reason="Filename must be provided",
            )
        key = self.request.path.replace("/", "_")
        try:
            # NB: this can't be collapsed into a one-liner!
            # for some reason doing it in one line yields a
            # 'released memoryview ...'
            shm = shared_memory.SharedMemory(name=key)
            buffer_contents = bytes(shm.buf)
        except FileNotFoundError:
            raise tornado.web.HTTPError(
                HTTPStatus.NOT_FOUND,
                reason="File not found",
            )
        # TODO(akshayka): can we encode mime-type in the path?
        # TODO: hack content-type to test ...
        self.set_header("Content-Type", "application/pdf")
        self.write(buffer_contents)
