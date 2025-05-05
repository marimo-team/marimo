# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._ast.toplevel import HINT_UNPARSABLE, TopLevelStatus
from marimo._messaging.ops import CellOp, VariableValue
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw


def test_value_ui_element() -> None:
    variable_value = VariableValue(name="s", value=slider(1, 10, value=5))
    assert variable_value.datatype == "slider"
    assert variable_value.value == "5"


def test_value_html() -> None:
    h = Html("<span></span>")
    variable_value = VariableValue(name="h", value=h)
    assert variable_value.datatype == "Html"
    assert variable_value.value == h.text


def test_variable_value_broken_str() -> None:
    class Broken:
        def __str__(self) -> str:
            raise BaseException  # noqa: TRY002

    variable_value = VariableValue(name="o", value=Broken())
    assert variable_value.datatype == "Broken"
    assert variable_value.value is not None
    assert variable_value.value.startswith("<Broken object at")


def test_broadcast_serialization() -> None:
    cell_id = CellId_t("test_cell_id")

    stream = MagicMock()
    stream.write = MagicMock()
    status = MagicMock(TopLevelStatus)
    status.hint = HINT_UNPARSABLE

    CellOp.broadcast_serialization(
        cell_id=cell_id, serialization=status, stream=stream
    )

    stream.write.assert_called_once()
    cell_op = stream.write.call_args.kwargs["data"]
    assert cell_op["serialization"] == str(HINT_UNPARSABLE)

    assert isinstance(parse_raw(cell_op, CellOp), CellOp)
