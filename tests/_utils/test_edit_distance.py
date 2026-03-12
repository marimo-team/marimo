# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.edit_distance import edit_distance


def test_edit_distance() -> None:
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("export", "export") == 0
