# Copyright 2024 Marimo. All rights reserved.
"""
Sanity check that tutorials are parsable / accessible.
"""

from __future__ import annotations

from marimo._tutorials import get_tutorial_source, tutorial_order


def test_tutorial_source() -> None:
    for tutorial in tutorial_order:
        source = get_tutorial_source(tutorial)
        assert source
