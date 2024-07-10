# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
from typing import get_args, Literal, Union


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
