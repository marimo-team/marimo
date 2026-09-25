# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.variables import demangle_locals_in_text, unmangle_local


def test_demangle_in_name_error_message() -> None:
    assert (
        demangle_locals_in_text(
            "NameError: name '_cell_vblA_a' is not defined"
        )
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


def test_demangle_handles_uuid_cell_id() -> None:
    # External / VSCode notebooks use `external_prefix()` (a uuid4) as the
    # cell-id prefix, producing hyphenated mangles.
    assert (
        demangle_locals_in_text(
            "NameError: name "
            "'_cell_c9bf9e57-1685-4c89-bafb-ff5af830be8a_a' "
            "is not defined"
        )
        == "NameError: name '_a' is not defined"
    )


def test_unmangle_local_handles_uuid_cell_id() -> None:
    # A cell hashes to the same digest wherever it is compiled only if the
    # name survives mangling identically, so hyphenated ids must unmangle.
    name, cell = unmangle_local("_cell_c9bf9e57-1685-4c89-bafb-1234abcd_a")
    assert name == "_a"
    assert cell == "c9bf9e57-1685-4c89-bafb-1234abcd"


def test_unmangle_local_leaves_an_unmangled_name_alone() -> None:
    assert unmangle_local("_a") == ("_a", "")
    assert unmangle_local("value") == ("value", "")


def test_demangle_handles_single_underscore_local() -> None:
    # `_` is a valid local name (variables.py:is_local); it mangles to
    # `_cell_<id>_` with no name suffix.
    assert (
        demangle_locals_in_text("NameError: name '_cell_Hbol_' is not defined")
        == "NameError: name '_' is not defined"
    )
