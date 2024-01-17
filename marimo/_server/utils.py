# Copyright 2023 Marimo. All rights reserved.
import os
import pathlib
import sys
from typing import Any

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    print(f"{TAB * n_tabs}{string}")


def canonicalize_filename(filename: str) -> str:
    if pathlib.Path(filename).suffix != ".py":
        filename += ".py"
    return os.path.expanduser(filename)


def import_files(filename: str) -> Any:
    if sys.version_info < (3, 9):
        from importlib_resources import files as importlib_files
    else:
        from importlib.resources import files as importlib_files

    return importlib_files(filename)


def initialize_mimetypes() -> None:
    import mimetypes

    # Fixes an issue with invalid mimetypes on windows:
    # https://github.com/encode/starlette/issues/829#issuecomment-587163696
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")
