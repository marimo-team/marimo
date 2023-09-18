# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import tornado.web

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._server import sessions
from marimo._server.api.model import parse_raw
from marimo._server.api.status import HTTPStatus
from marimo._server.layout import LayoutConfig, save_layout_config
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()


@dataclass
class Save:
    # code for each cell
    codes: List[str]
    # name of each cell
    names: List[str]
    # config for each cell
    configs: List[CellConfig]
    # path to app
    filename: str
    # layout of app
    layout: Optional[Dict[str, Any]] = None


class SaveHandler(tornado.web.RequestHandler):
    """Save an app to disk."""

    @sessions.requires_edit
    def post(self) -> None:
        mgr = sessions.get_manager()
        args = parse_raw(self.request.body, Save)
        codes, names, filename, layout = (
            args.codes,
            args.names,
            args.filename,
            args.layout,
        )
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
            # save layout
            if layout is not None:
                app_dir = os.path.dirname(filename)
                app_name = os.path.basename(filename)
                layout_filename = save_layout_config(
                    app_dir, app_name, LayoutConfig(**layout)
                )
                mgr.update_app_config({"layout_file": layout_filename})

            # try to save the app under the name `filename`
            contents = codegen.generate_filecontents(
                codes, names, cell_configs=args.configs, config=mgr.app_config
            )
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
