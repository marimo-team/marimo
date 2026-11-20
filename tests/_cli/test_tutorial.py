# Copyright 2026 Marimo. All rights reserved.
"""
Sanity check that tutorials are parsable / accessible.
"""

from __future__ import annotations

from typing import get_args

from marimo._tutorials import Tutorial, get_tutorial_source, tutorial_order


def test_tutorial_order_lists_every_tutorial() -> None:
    expected = {
        tutorial
        for variant in get_args(Tutorial)
        for tutorial in get_args(variant)
    }
    assert sorted(tutorial_order) == sorted(expected)


def test_tutorial_source() -> None:
    for tutorial in tutorial_order:
        source = get_tutorial_source(tutorial)
        assert source
