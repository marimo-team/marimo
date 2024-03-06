from __future__ import annotations

import importlib
import os.path

from marimo._output.formatters.formatters import register_formatters


def test_path_finder_find_spec() -> None:
    # exercises a bug surfaced in
    # https://github.com/marimo-team/marimo/issues/763, in which find_spec
    # would fail because it was incorrectly patched
    register_formatters()

    spec = importlib.machinery.PathFinder.find_spec(
        "test_formatters", [os.path.dirname(__file__)]
    )
    assert spec is not None
