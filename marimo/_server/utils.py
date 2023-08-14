# Copyright 2023 Marimo. All rights reserved.
import os
import pathlib

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
