# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
from typing import TYPE_CHECKING, Literal, get_args

from marimo._utils.marimo_path import MarimoPath, create_temp_notebook_file

if TYPE_CHECKING:
    import tempfile

PythonTutorial = Literal[
    "intro",
    "dataflow",
    "ui",
    "markdown",
    "plots",
    "sql",
    "layout",
    "fileformat",
    "external-dependencies",
    "for-jupyter-users",
]

MarkdownTutorial = Literal["markdown-format"]
Tutorial = PythonTutorial | MarkdownTutorial
tutorial_order: list[Tutorial] = [
    "intro",
    "dataflow",
    "ui",
    "markdown",
    "plots",
    "sql",
    "layout",
    "fileformat",
    "external-dependencies",
    "markdown-format",
    "for-jupyter-users",
]
if set(tutorial_order) != set(get_args(PythonTutorial)) | set(
    get_args(MarkdownTutorial)
):
    raise RuntimeError("Tutorial missing")


def get_tutorial_source(name: Tutorial) -> str:
    if name in get_args(PythonTutorial):
        module_name = name.replace("-", "_")
        # from marimo._tutorials import <name>
        tutorial = getattr(
            __import__("marimo._tutorials", fromlist=[module_name]),
            module_name,
        )
        return inspect.getsource(tutorial)
    if name not in get_args(MarkdownTutorial):
        raise ValueError(f"Unknown tutorial: {name}")
    module_name = name.replace("-", "_")
    file = os.path.join(os.path.dirname(__file__), f"{module_name}.md")
    with open(file, encoding="utf8") as f:
        return f.read()


def create_temp_tutorial_file(
    name: Tutorial, temp_dir: tempfile.TemporaryDirectory[str]
) -> MarimoPath:
    source = get_tutorial_source(name)
    extension: Literal["py", "md"] = (
        "py" if name in get_args(PythonTutorial) else "md"
    )
    return create_temp_notebook_file(name, extension, source, temp_dir)
