# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.variables import demangle_locals_in_text


def test_demangle_in_name_error_message() -> None:
    assert (
        demangle_locals_in_text("NameError: name '_cell_vblA_a' is not defined")
        == "NameError: name '_a' is not defined"
    )


def test_demangle_handles_multi_segment_names() -> None:
    assert (
        demangle_locals_in_text("_cell_AAAA_x and _cell_BBBB_y_z")
        == "_x and _y_z"
    )


def test_demangle_leaves_cell_file_path_alone() -> None:
    path = "/tmp/marimo_42/__marimo__cell_Hbol_.py"
    assert demangle_locals_in_text(path) == path


def test_demangle_no_op_for_plain_text() -> None:
    assert demangle_locals_in_text("plain text") == "plain text"
