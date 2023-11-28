# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import tornado.web

from marimo._server import sessions
from marimo._server.api.status import HTTPStatus
from marimo._server.api.validated_handler import ValidatedHandler


class ReadCodeHandler(ValidatedHandler):
    """Handler for reading code from the server."""

    @sessions.requires_edit
    def post(self) -> None:
        mgr = sessions.get_manager()
        if mgr.filename is None:
            raise tornado.web.HTTPError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                reason="Cannot read code from an unnamed notebook",
            )
        try:
            with open(mgr.filename, "r", encoding="utf-8") as f:
                contents = f.read().strip()
        except Exception as e:
            raise tornado.web.HTTPError(
                HTTPStatus.SERVER_ERROR,
                reason="Failed to read file: {0}".format(str(e)),
            ) from e

        self.write({"contents": contents})
