# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
import tempfile
from typing import get_args, Literal, Union

from marimo._utils.marimo_path import MarimoPath


PythonTutorial = Literal[
    "intro",
    "dataflow",
    "ui",
    "markdown",
    "plots",
    "sql",
    "layout",
    "fileformat",
    "for-jupyter-users",
]

MarkdownTutorial = Literal["markdown-format",]
Tutorial = Union[PythonTutorial, MarkdownTutorial]
tutorial_order: list[Tutorial] = [
    "intro",
    "dataflow",
    "ui",
    "markdown",
    "plots",
    "sql",
    "layout",
    "fileformat",
    "markdown-format",
    "for-jupyter-users",
]
assert set(tutorial_order) == set(get_args(PythonTutorial)) | set(get_args(MarkdownTutorial)), "Tutorial missing"


def get_tutorial_source(name: Tutorial) -> str:
    if name in get_args(PythonTutorial):
        name = name.replace("-", "_")
        # from marimo._tutorials import <name>
        tutorial = getattr(__import__("marimo._tutorials", fromlist=[name]),
                           name)
        return inspect.getsource(tutorial)
    assert name in get_args(MarkdownTutorial)
    name = name.replace("-", "_")
    file = os.path.join(os.path.dirname(__file__), f"{name}.md")
    with open(file, "r", encoding="utf8") as f:
        return f.read()

def create_temp_tutorial_file(name: Tutorial, temp_dir: tempfile.TemporaryDirectory[str]) -> MarimoPath:
    source = get_tutorial_source(name)
    extension = "py" if name in get_args(PythonTutorial) else "md"
    fname = os.path.join(temp_dir.name, f"{name}.{extension}")
    path = MarimoPath(fname)
    path.write_text(source)
    return path
