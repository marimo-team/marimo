# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from starlette.exceptions import HTTPException

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, InternalApp
from marimo._ast.cell import CellConfig
from marimo._runtime.layout.layout import LayoutConfig, save_layout_config
from marimo._server.api.status import HTTPStatus
from marimo._server.models.models import (
    SaveRequest,
)
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()


class AppFileManager:
    def __init__(self, filename: Optional[str]) -> None:
        self.filename = filename
        self.path = self._get_file_path(filename)
        self.app = self._load_app(self.path)

    @staticmethod
    def from_app(app: InternalApp) -> AppFileManager:
        manager = AppFileManager(None)
        manager.app = app
        return manager

    def reload(self) -> None:
        """Reload the app from the file."""
        self.app = self._load_app(self.path)

    @staticmethod
    def _load_app(path: Optional[str]) -> InternalApp:
        """Read the app from the file."""
        app = codegen.get_app(path)
        if app is None:
            empty_app = InternalApp(App())
            empty_app.cell_manager.register_cell(
                cell_id=None,
                code="",
                config=CellConfig(),
            )
            return empty_app

        return InternalApp(app)

    def rename(self, new_filename: str) -> None:
        """Rename the file."""

        new_filename = canonicalize_filename(new_filename)

        if self.filename == new_filename:
            return
        if os.path.exists(new_filename):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="File {0} already exists".format(new_filename),
            )
        if self.filename is not None:
            try:
                os.rename(self.filename, new_filename)
            except Exception as err:
                raise HTTPException(
                    status_code=HTTPStatus.SERVER_ERROR,
                    detail="Failed to rename from {0} to {1}".format(
                        self.filename, new_filename
                    ),
                ) from err
        else:
            try:
                # create a file named `new_filename`
                with open(new_filename, "w") as _:
                    pass
            except Exception as err:
                raise HTTPException(
                    status_code=HTTPStatus.SERVER_ERROR,
                    detail="Failed to create file {0}".format(new_filename),
                ) from err

        self.filename = new_filename
        self.path = self._get_file_path(new_filename)

    @staticmethod
    def _get_file_path(filename: Optional[str]) -> Optional[str]:
        if filename is None:
            return None
        try:
            return os.path.abspath(filename)
        except AttributeError:
            return None

    def save_app_config(self, config: Dict[str, Any]) -> None:
        """Save the app configuration."""
        # Update the file with the latest app config
        # TODO(akshayka): Only change the `app = marimo.App` line (at top level
        # of file), instead of overwriting the whole file.
        new_config = self.app.update_config(config)

        if self.filename is not None:
            # Try to save the app under the name `self.filename`
            contents = codegen.generate_filecontents(
                codes=list(self.app.cell_manager.codes()),
                names=list(self.app.cell_manager.names()),
                cell_configs=list(self.app.cell_manager.configs()),
                config=new_config,
            )
            try:
                with open(self.filename, "w", encoding="utf-8") as f:
                    f.write(contents)
            except Exception as e:
                raise HTTPException(
                    status_code=HTTPStatus.SERVER_ERROR,
                    detail="Failed to save file: {0}".format(str(e)),
                ) from e

    def save(self, request: SaveRequest) -> None:
        """Save the current app."""
        cell_ids, codes, configs, names, filename, layout = (
            request.cell_ids,
            request.codes,
            request.configs,
            request.names,
            request.filename,
            request.layout,
        )
        filename = canonicalize_filename(filename)
        self.app.with_data(
            cell_ids=cell_ids,
            codes=codes,
            names=names,
            configs=configs,
        )

        if self.filename is not None and self.filename != filename:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Save handler cannot rename files.",
            )
        elif self.filename is None and os.path.exists(filename):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="File {0} already exists".format(filename),
            )
        else:
            # save layout
            if layout is not None:
                app_dir = os.path.dirname(filename)
                app_name = os.path.basename(filename)
                layout_filename = save_layout_config(
                    app_dir, app_name, LayoutConfig(**layout)
                )
                self.app.update_config({"layout_file": layout_filename})

            # try to save the app under the name `filename`
            contents = codegen.generate_filecontents(
                codes,
                names,
                cell_configs=configs,
                config=self.app.config,
            )

            LOGGER.debug("Saving app to %s", filename)
            try:
                header_comments = codegen.get_header_comments(filename)
                with open(filename, "w", encoding="utf-8") as f:
                    if header_comments:
                        f.write(header_comments.rstrip() + "\n\n")
                    f.write(contents)
            except Exception as e:
                raise HTTPException(
                    status_code=HTTPStatus.SERVER_ERROR,
                    detail="Failed to save file: {0}".format(str(e)),
                ) from e
            if self.filename is None:
                self.rename(filename)

    def read_file(self) -> str:
        """Read the contents of the file."""
        if self.filename is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Cannot read code from an unnamed notebook",
            )
        with open(self.filename, "r", encoding="utf-8") as f:
            contents = f.read().strip()
        return contents
