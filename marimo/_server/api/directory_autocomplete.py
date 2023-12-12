# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass

from marimo._server import sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class DirectoryAutocomplete:
    prefix: str


class DirectoryAutocompleteHandler(ValidatedHandler):
    """Complete a path to subdirectories and Python files."""

    @sessions.requires_edit
    def post(self) -> None:
        args = parse_raw(self.request.body, DirectoryAutocomplete)
        directory = os.path.dirname(args.prefix)
        if not directory:
            directory = "."

        try:
            subdirectories, files = next(os.walk(directory))[1:]
        except StopIteration:
            self.write({"directories": [], "files": []})
            return

        basename = os.path.basename(args.prefix)
        directories = sorted(
            [d for d in subdirectories if d.startswith(basename)]
        )
        files = sorted(
            [f for f in files if f.startswith(basename) and f.endswith(".py")]
        )
        self.write(
            {
                "directories": directories,
                "files": files,
            }
        )
