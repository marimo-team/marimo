# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Final,
)

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    from numpy.typing import ArrayLike


def _to_nested_list(
    value: list[list[float]] | ArrayLike,
) -> list[list[float]]:
    """Convert a value to a nested list of floats.

    Accepts list[list[float]] or numpy-array-like (anything with .tolist()).
    """
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        raise ValueError(
            f"`value` must be a list of lists or array-like, got {type(value)}"
        )
    if len(value) == 0:
        raise ValueError("`value` must be non-empty")
    for i, row in enumerate(value):
        if not isinstance(row, (list, tuple)):
            raise ValueError(
                f"Each row of `value` must be a list, "
                f"but row {i} has type {type(row)}"
            )
    return [[float(x) for x in row] for row in value]


def _broadcast_param(
    name: str,
    param: float | list[list[float]] | ArrayLike | None,
    rows: int,
    cols: int,
    *,
    allow_none: bool = False,
) -> list[list[float]] | None:
    """Broadcast a scalar or array-like param to a rows x cols matrix.

    Returns None if param is None and allow_none is True.
    """
    if param is None:
        if allow_none:
            return None
        raise ValueError(f"`{name}` cannot be None")

    # Convert array-like
    if hasattr(param, "tolist"):
        param = param.tolist()

    # Scalar broadcast
    if isinstance(param, (int, float)):
        return [[float(param)] * cols for _ in range(rows)]

    # Must be a nested list
    if not isinstance(param, list):
        raise ValueError(
            f"`{name}` must be a scalar, nested list, or array-like, "
            f"got {type(param)}"
        )
    if len(param) != rows:
        raise ValueError(f"`{name}` has {len(param)} rows but expected {rows}")
    for i, row in enumerate(param):
        if not isinstance(row, (list, tuple)):
            raise ValueError(
                f"`{name}` row {i} must be a list, got {type(row)}"
            )
        if len(row) != cols:
            raise ValueError(
                f"`{name}` row {i} has {len(row)} columns but expected {cols}"
            )
    return [[float(x) for x in row] for row in param]


def _broadcast_bool_param(
    name: str,
    param: bool | list[list[bool]] | ArrayLike,
    rows: int,
    cols: int,
) -> list[list[bool]]:
    """Broadcast a scalar or array-like bool param to a rows x cols matrix."""
    if hasattr(param, "tolist"):
        param = param.tolist()

    if isinstance(param, bool):
        return [[param] * cols for _ in range(rows)]

    if not isinstance(param, list):
        raise ValueError(
            f"`{name}` must be a bool, nested list, or array-like, "
            f"got {type(param)}"
        )
    if len(param) != rows:
        raise ValueError(f"`{name}` has {len(param)} rows but expected {rows}")
    for i, row in enumerate(param):
        if not isinstance(row, (list, tuple)):
            raise ValueError(
                f"`{name}` row {i} must be a list, got {type(row)}"
            )
        if len(row) != cols:
            raise ValueError(
                f"`{name}` row {i} has {len(row)} columns but expected {cols}"
            )
    return [[bool(x) for x in row] for row in param]


@mddoc
class matrix(UIElement[list[list[float]], list[list[float]]]):
    """An interactive matrix editor.

    Renders a grid of numeric cells with bracket decorations (like math
    notation). Users click and drag horizontally on a cell to
    increment/decrement its value.

    Examples:
        ```python
        # 2x2 identity matrix
        mat = mo.ui.matrix([[1, 0], [0, 1]])
        ```

        ```python
        # 3x3 zeros with bounds
        mat = mo.ui.matrix(
            [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            min_value=-10,
            max_value=10,
            step=0.5,
        )
        ```

        The value, bounds, step, and disabled arguments can optionally be NumPy
        arrays, interpreted elementwise.

        ```python
        # Initialize from a numpy array
        import numpy as np

        mat = mo.ui.matrix(np.eye(3), step=0.1)
        ```

        ```python
        # Per-element bounds and step using numpy arrays
        import numpy as np

        mat = mo.ui.matrix(
            np.zeros((3, 3)),
            min_value=np.full((3, 3), -10.0),
            max_value=np.full((3, 3), 10.0),
            step=np.full((3, 3), 0.5),
        )
        ```

        ```python
        import numpy as np

        mat = mo.ui.matrix(np.eye(2))
        ```

        ```
        array = np.asarray(mat.value)
        ```

    Attributes:
        value (list[list[float]]): The current 2D matrix as a nested list.
            Use `np.asarray(matrix.value)` to convert to a numpy array.

    Args:
        value (list[list[float]] | ArrayLike): Initial 2D matrix data.
            Accepts a nested list of numbers or a numpy array. Rows and
            columns are inferred from the shape.
        min_value (float | list[list[float]] | ArrayLike | None, optional):
            Minimum allowed value. A scalar is broadcast to all cells; a
            nested list or numpy array sets per-element bounds. None means
            unbounded. Defaults to None.
        max_value (float | list[list[float]] | ArrayLike | None, optional):
            Maximum allowed value. A scalar is broadcast to all cells; a
            nested list or numpy array sets per-element bounds. None means
            unbounded. Defaults to None.
        step (float | list[list[float]] | ArrayLike, optional): Drag
            increment. A scalar is broadcast to all cells; a nested list
            or numpy array sets per-element step sizes. Defaults to 1.0.
        precision (int, optional): Number of decimal places displayed.
            Defaults to 3.
        row_labels (list[str] | None, optional): Labels for each row.
            Defaults to None.
        column_labels (list[str] | None, optional): Labels for each column.
            Defaults to None.
        symmetric (bool, optional): If True, editing cell [i][j] also
            updates cell [j][i]. Requires a square matrix. Defaults to False.
        label (str, optional): Markdown label for the element.
            Defaults to "".
        scientific (bool, optional): If True, display values in scientific
            notation (e.g., `1.0e-4`). Defaults to False.
        on_change (Callable | None, optional): Optional callback to run
            when this element's value changes.
        disabled (bool | list[list[bool]] | ArrayLike, optional): Whether
            cells are disabled. A scalar bool is broadcast to all cells; a
            nested list or numpy bool array sets a per-element mask.
            Defaults to False.
    """

    _name: Final[str] = "marimo-matrix"

    def __init__(
        self,
        value: list[list[float]] | ArrayLike,
        *,
        min_value: float | list[list[float]] | ArrayLike | None = None,
        max_value: float | list[list[float]] | ArrayLike | None = None,
        step: float | list[list[float]] | ArrayLike = 1.0,
        precision: int = 1,
        row_labels: list[str] | None = None,
        column_labels: list[str] | None = None,
        symmetric: bool = False,
        scientific: bool = False,
        label: str = "",
        on_change: Callable[[list[list[float]]], None] | None = None,
        disabled: bool | list[list[bool]] | ArrayLike = False,
    ) -> None:
        # Convert and validate value
        data = _to_nested_list(value)
        rows = len(data)
        cols = len(data[0])

        # Validate consistent row lengths
        for i, row in enumerate(data):
            if len(row) != cols:
                raise ValueError(
                    f"All rows must have the same length. "
                    f"Row 0 has {cols} columns but row {i} has {len(row)}"
                )

        # Broadcast and validate params
        min_val = _broadcast_param(
            "min_value", min_value, rows, cols, allow_none=True
        )
        max_val = _broadcast_param(
            "max_value", max_value, rows, cols, allow_none=True
        )
        step_val = _broadcast_param("step", step, rows, cols)
        disabled_val = _broadcast_bool_param("disabled", disabled, rows, cols)

        # Validate min < max where both are specified
        if min_val is not None and max_val is not None:
            for i in range(rows):
                for j in range(cols):
                    if min_val[i][j] >= max_val[i][j]:
                        raise ValueError(
                            f"`min_value` ({min_val[i][j]}) must be less "
                            f"than `max_value` ({max_val[i][j]}) at "
                            f"position [{i}][{j}]"
                        )

        # Validate initial value is within bounds
        if min_val is not None:
            for i in range(rows):
                for j in range(cols):
                    if data[i][j] < min_val[i][j]:
                        raise ValueError(
                            f"Initial value {data[i][j]} at [{i}][{j}] is "
                            f"less than min_value {min_val[i][j]}"
                        )
        if max_val is not None:
            for i in range(rows):
                for j in range(cols):
                    if data[i][j] > max_val[i][j]:
                        raise ValueError(
                            f"Initial value {data[i][j]} at [{i}][{j}] is "
                            f"greater than max_value {max_val[i][j]}"
                        )

        # Validate label lengths
        if row_labels is not None and len(row_labels) != rows:
            raise ValueError(
                f"`row_labels` has {len(row_labels)} entries "
                f"but matrix has {rows} rows"
            )
        if column_labels is not None and len(column_labels) != cols:
            raise ValueError(
                f"`column_labels` has {len(column_labels)} entries "
                f"but matrix has {cols} columns"
            )

        # Validate symmetric requires square matrix
        if symmetric and rows != cols:
            raise ValueError(
                f"`symmetric` requires a square matrix, but got {rows}x{cols}"
            )

        if not isinstance(precision, int) or precision < 0:
            raise ValueError(
                f"`precision` must be a non-negative integer, got {precision}"
            )

        super().__init__(
            component_name=matrix._name,
            initial_value=data,
            label=label,
            args={
                "min-value": min_val,
                "max-value": max_val,
                "step": step_val,
                "precision": precision,
                "row-labels": row_labels,
                "column-labels": column_labels,
                "symmetric": symmetric,
                "scientific": scientific,
                "disabled": disabled_val,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: list[list[float]]) -> list[list[float]]:
        return value
