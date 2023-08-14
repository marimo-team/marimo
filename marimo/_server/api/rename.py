# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass

import tornado.web

from marimo import _loggers
from marimo._server import sessions
from marimo._server.api import status
from marimo._server.api.model import parse_raw
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()


@dataclass
class Rename:
    filename: str


class RenameHandler(tornado.web.RequestHandler):
    """Rename the current app."""

    @sessions.requires_edit
    def post(self) -> None:
        mgr = sessions.get_manager()
        args = parse_raw(self.request.body, Rename)
        filename = args.filename
        LOGGER.debug("Renaming from %s to %s", mgr.filename, filename)
        if filename is not None:
            filename = canonicalize_filename(filename)

        if filename == mgr.filename:
            # no-op
            pass
        elif filename is None:
            mgr.rename(filename)
        elif os.path.exists(filename):
            raise tornado.web.HTTPError(
                status.HTTPStatus.METHOD_NOT_ALLOWED,
                reason="File {0} already exists".format(filename),
            )
        elif mgr.filename is None:
            try:
                # create a file named `filename`
                with open(filename, "w") as _:
                    pass
            except Exception as err:
                raise tornado.web.HTTPError(
                    status.HTTPStatus.SERVER_ERROR,
                    reason="Failed to create file {0}".format(filename),
                ) from err
            mgr.rename(filename)
        else:
            try:
                os.rename(mgr.filename, filename)
            except Exception as err:
                raise tornado.web.HTTPError(
                    status.HTTPStatus.SERVER_ERROR,
                    reason="Failed to rename from {0} to {1}".format(
                        mgr.filename, filename
                    ),
                ) from err
            mgr.rename(filename)
