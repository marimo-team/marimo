# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass

import tornado.web

from marimo import _loggers
from marimo._ast import codegen
from marimo._server import sessions
from marimo._server.api.model import parse_raw
from marimo._server.api.status import HTTPStatus
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()


@dataclass
class Save:
    # code for each cell
    codes: list[str]
    # name of each cell
    names: list[str]
    # path to app
    filename: str


class SaveHandler(tornado.web.RequestHandler):
    """Save an app to disk."""

    @sessions.requires_edit
    def post(self) -> None:
        mgr = sessions.get_manager()
        args = parse_raw(self.request.body, Save)
        codes, names, filename = args.codes, args.names, args.filename
        filename = canonicalize_filename(filename)
        if mgr.filename is not None and mgr.filename != filename:
            raise tornado.web.HTTPError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                reason="Save handler cannot rename files.",
            )
        elif mgr.filename is None and os.path.exists(filename):
            raise tornado.web.HTTPError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                reason="File {0} already exists".format(filename),
            )
        else:
            # try to save the app under the name `filename`
            contents = codegen.generate_filecontents(codes, names)
            LOGGER.debug("Saving app to %s", filename)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(contents)
            except Exception as e:
                raise tornado.web.HTTPError(
                    HTTPStatus.SERVER_ERROR,
                    reason="Failed to save file: {0}".format(str(e)),
                ) from e
            if mgr.filename is None:
                mgr.rename(filename)
