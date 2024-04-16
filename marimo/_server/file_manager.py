# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, InternalApp
from marimo._ast.cell import CellConfig
from marimo._runtime.layout.layout import (
    LayoutConfig,
    read_layout_config,
    save_layout_config,
)
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.models.models import (
    SaveRequest,
)
from marimo._server.utils import canonicalize_filename

LOGGER = _loggers.marimo_logger()


class AppFileManager:
    def __init__(self, filename: Optional[str]) -> None:
        self.filename = filename
        self.app = self._load_app(self.path)

    @staticmethod
    def from_app(app: InternalApp) -> AppFileManager:
        manager = AppFileManager(None)
        manager.app = app
        return manager

    def reload(self) -> None:
        """Reload the app from the file."""
        self.app = self._load_app(self.path)

    def _is_same_path(self, filename: str) -> bool:
        if self.filename is None:
            return False
        return os.path.abspath(self.filename) == os.path.abspath(filename)

    def _assert_path_does_not_exist(self, filename: str) -> None:
        if os.path.exists(filename):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="File {0} already exists".format(filename),
            )

    def _assert_path_is_the_same(self, filename: str) -> None:
        if self.filename is not None and not self._is_same_path(filename):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Save handler cannot rename files.",
            )

    def _create_file(
        self,
        filename: str,
        contents: str = "",
        header_comments: Optional[str] = None,
    ) -> None:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                if header_comments:
                    f.write(header_comments.rstrip() + "\n\n")
                f.write(contents)
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to save file {0}".format(filename),
            ) from err

    def _rename_file(self, new_filename: str) -> None:
        assert self.filename is not None
        try:
            os.rename(self.filename, new_filename)
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail="Failed to rename from {0} to {1}".format(
                    self.filename, new_filename
                ),
            ) from err

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

        if self._is_same_path(new_filename):
            return

        self._assert_path_does_not_exist(new_filename)

        if self.filename is not None:
            self._rename_file(new_filename)
        else:
            self._create_file(new_filename)

        self.filename = new_filename

    def read_layout_config(self) -> Optional[LayoutConfig]:
        if self.app.config.layout_file is not None and isinstance(
            self.filename, str
        ):
            app_dir = os.path.dirname(self.filename)
            layout = read_layout_config(app_dir, self.app.config.layout_file)
            return layout

        return None

    @property
    def path(self) -> Optional[str]:
        if self.filename is None:
            return None
        try:
            return os.path.abspath(self.filename)
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
            header_comments = codegen.get_header_comments(self.filename)
            self._create_file(self.filename, contents, header_comments)

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

        if self.filename is not None and not self._is_same_path(filename):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Save handler cannot rename files.",
            )

        # save layout
        if layout is not None:
            app_dir = os.path.dirname(filename)
            app_name = os.path.basename(filename)
            layout_filename = save_layout_config(
                app_dir, app_name, LayoutConfig(**layout)
            )
            self.app.update_config({"layout_file": layout_filename})
        else:
            # Remove the layout from the config
            # We don't remove the layout file from the disk to avoid
            # deleting state that the user might want to keep
            self.app.update_config({"layout_file": None})
        # try to save the app under the name `filename`
        contents = codegen.generate_filecontents(
            codes,
            names,
            cell_configs=configs,
            config=self.app.config,
        )
        LOGGER.debug("Saving app to %s", filename)
        header_comments = codegen.get_header_comments(filename)
        self._create_file(filename, contents, header_comments)

        if self.filename is None:
            self.rename(filename)

    def to_code(self) -> str:
        """Read the contents of the unsaved file."""
        contents = codegen.generate_filecontents(
            codes=list(self.app.cell_manager.codes()),
            names=list(self.app.cell_manager.names()),
            cell_configs=list(self.app.cell_manager.configs()),
            config=self.app.config,
        )
        return contents

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
