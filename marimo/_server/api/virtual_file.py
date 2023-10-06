# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
from multiprocessing import shared_memory

import tornado.web

from marimo import _loggers
from marimo._server.api.status import HTTPStatus

LOGGER = _loggers.marimo_logger()


class VirtualFileHandler(tornado.web.RequestHandler):
    """Handler for virtual files."""

    def get(self, filename: str) -> None:
        key = filename
        shm = None
        try:
            # NB: this can't be collapsed into a one-liner!
            # doing it in one line yields a 'released memoryview ...'
            # because shared_memory has built in ref-tracking + GC
            shm = shared_memory.SharedMemory(name=key)
            buffer_contents = bytes(shm.buf)
        except FileNotFoundError as err:
            raise tornado.web.HTTPError(
                HTTPStatus.NOT_FOUND,
                reason="File not found",
            ) from err
        finally:
            if shm is not None:
                shm.close()
        mimetype, _ = mimetypes.guess_type(filename)
        if mimetype is not None:
            self.set_header("Content-Type", mimetype)
        self.set_header("Cache-Control", "max-age=86400")
        self.write(buffer_contents)
