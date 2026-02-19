# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
)

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    from numpy.typing import ArrayLike


Numeric = int | float


def _broadcast(
    name: str,
    param: Any,
    rows: int,
    cols: int,
) -> list[list[Any]]:
    """Broadcast a scalar, nested list, or array-like to a rows x cols matrix.

    *convert* is applied to every cell (e.g. `float` or `bool`).
    """
    if hasattr(param, "tolist"):
        param = param.tolist()

    if not isinstance(param, list):
        return [[param] * cols for _ in range(rows)]

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
        for j, cell in enumerate(row):
            if isinstance(cell, (list, tuple)):
                raise ValueError(
                    f"`{name}` must be 2D, but found a nested "
                    f"sequence at position [{i}][{j}]"
                )
    return param


def _to_nested_list(
    value: list[list[Numeric]] | ArrayLike,
) -> list[list[Numeric]]:
    """Parse and validate initial matrix data into a nested list.

    Accepts a nested list of numbers or a numpy array-like with `.tolist()`.
    Rejects empty, non-2D, or ragged inputs.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list):
        raise ValueError(
            f"`value` must be a list of lists or array-like, got {type(value)}"
        )

    if not value:
        raise ValueError("`value` must be non-empty")

    first = value[0]
    if not isinstance(first, (list, tuple)) or not first:
        raise ValueError(
            f"`value` must contain non-empty lists, but row 0 is {first!r}"
        )
    return _broadcast("value", value, len(value), len(first))


def _decimal_places(x: Numeric) -> int:
    """Count decimal places needed in fixed notation."""
    if isinstance(x, int) or x == int(x):
        return 0
    s = repr(x)
    if "e" in s or "E" in s:
        parts = s.lower().split("e")
        exp = int(parts[1])
        mantissa_dec = len(parts[0].split(".")[1]) if "." in parts[0] else 0
        return max(0, mantissa_dec - exp)
    if "." in s:
        return len(s.split(".")[1])
    return 0


def _mantissa_decimal_places(x: Numeric) -> int:
    """Count decimal places needed in the mantissa for scientific notation.

    For example, `0.00153` → `1.53e-3` → 2 mantissa places,
    while `1e-8` → `1e-8` → 0 mantissa places.
    """
    if isinstance(x, int):
        # Strip trailing zeros: 1234000 → 1.234e6 → 3 places
        if x == 0:
            return 0
        s = str(abs(x)).rstrip("0")
        return max(0, len(s) - 1)
    if x == 0.0:
        return 0
    # Format with enough mantissa digits, then strip trailing zeros
    s = f"{x:.15e}"  # e.g. "1.530000000000000e-03"
    mantissa = s.split("e")[0].rstrip("0").rstrip(".")
    if "." in mantissa:
        return len(mantissa.split(".")[1])
    return 0


def _infer_precision(
    data: list[list[Numeric]],
    step_val: list[list[Any]],
    scientific: bool,
) -> int:
    """Choose a display precision based on the data values and step sizes.

    When *scientific* is True, counts mantissa decimal places (e.g.
    `0.00153` needs 2 for `1.53e-3`).  Otherwise counts total
    decimal places in fixed notation (`0.00153` needs 5).
    """
    counter = _mantissa_decimal_places if scientific else _decimal_places
    best = 0
    for row in data:
        for v in row:
            best = max(best, counter(v))
    for row in step_val:
        for v in row:
            best = max(best, counter(v))
    return best


def _validate_and_build_args(
    data: list[list[Numeric]],
    *,
    min_val: list[list[Numeric]] | None,
    max_val: list[list[Numeric]] | None,
    step_val: list[list[Any]],
    disabled_val: list[list[Any]],
    symmetric: bool,
    scientific: bool,
    precision: int | None,
    row_labels: list[str] | None,
    column_labels: list[str] | None,
    debounce: bool,
) -> dict[str, Any]:
    """Validate matrix parameters and return the args dict for UIElement."""
    rows = len(data)
    cols = len(data[0])

    if precision is None:
        precision = _infer_precision(data, step_val, scientific)

    # Validate per-cell constraints in a single pass
    for i in range(rows):
        for j in range(cols):
            if step_val[i][j] <= 0:
                raise ValueError(
                    f"`step` must be positive, got {step_val[i][j]} "
                    f"at position [{i}][{j}]"
                )
            if min_val is not None and max_val is not None:
                if min_val[i][j] >= max_val[i][j]:
                    raise ValueError(
                        f"`min_value` ({min_val[i][j]}) must be less "
                        f"than `max_value` ({max_val[i][j]}) at "
                        f"position [{i}][{j}]"
                    )
            if min_val is not None and data[i][j] < min_val[i][j]:
                raise ValueError(
                    f"Initial value {data[i][j]} at [{i}][{j}] is "
                    f"less than min_value {min_val[i][j]}"
                )
            if max_val is not None and data[i][j] > max_val[i][j]:
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

    # Validate symmetric requires square matrix with symmetric data
    if symmetric:
        if rows != cols:
            raise ValueError(
                f"`symmetric` requires a square matrix, but got {rows}x{cols}"
            )
        for i in range(rows):
            for j in range(i + 1, cols):
                if data[i][j] != data[j][i]:
                    raise ValueError(
                        f"`symmetric` is True but initial data is not "
                        f"symmetric: value[{i}][{j}]={data[i][j]} != "
                        f"value[{j}][{i}]={data[j][i]}"
                    )

    if not isinstance(precision, int) or precision < 0:
        raise ValueError(
            f"`precision` must be a non-negative integer, got {precision}"
        )

    return {
        "min-value": min_val,
        "max-value": max_val,
        "step": step_val,
        "precision": precision,
        "row-labels": row_labels,
        "column-labels": column_labels,
        "symmetric": symmetric,
        "debounce": debounce,
        "scientific": scientific,
        "disabled": disabled_val,
    }


@mddoc
class matrix(UIElement[list[list[Numeric]], list[list[Numeric]]]):
    """An interactive matrix editor.

    A matrix UI element in which each entry is a slider: click and drag
    horizontally on an entry to increment or decrement its value. The
    matrix can be configured in many ways, including element-wise
    bounds, element-wise steps, an element-wise disable mask, and
    symmetry enforcement.

    Examples:
        Basic usage:

        ```python
        mat = mo.ui.matrix([[1, 0], [0, 1]])
        mat
        ```

        Access the value in another cell with

        ```python
        mat.value
        ```

        You can specify bounds and a step size as well:

        ```python
        mat = mo.ui.matrix(
            [[1, 0], [0, 1]],
            min_value=-10,
            max_value=10,
            step=0.5,
        )
        ```

        To disable editing of some or all entries, use the disabled argument:

        ```python
        mat = mo.ui.matrix(
            [[1, 0], [0, 1]],
            # Disable editing the diagonal values
            disabled=[[True, False], [False, True]],
        )
        ```

        The value, bounds, step, and disabled arguments can optionally be NumPy
        arrays, interpreted elementwise.

        ```python
        import numpy as np

        mat = mo.ui.matrix(np.eye(2))
        mat
        ```

        ```
        np.asarray(mat.value)
        ```

    Attributes:
        value (list[list[Numeric]]): The current 2D matrix as a nested list.
            Use `np.asarray(matrix.value)` to convert to a numpy array.

    Args:
        value (list[list[Numeric]] | ArrayLike): Initial 2D matrix data.
            Accepts a nested list of numbers or a numpy array. Rows and
            columns are inferred from the shape.
        min_value (Numeric | list[list[Numeric]] | ArrayLike | None, optional):
            Minimum allowed value. A scalar is broadcast to all cells; a
            nested list or numpy array sets per-element bounds. None means
            unbounded. Defaults to None.
        max_value (Numeric | list[list[Numeric]] | ArrayLike | None, optional):
            Maximum allowed value. A scalar is broadcast to all cells; a
            nested list or numpy array sets per-element bounds. None means
            unbounded. Defaults to None.
        step (Numeric | list[list[Numeric]] | ArrayLike, optional): Drag
            increment. A scalar is broadcast to all cells; a nested list
            or numpy array sets per-element step sizes. Defaults to 1.0.
        disabled (bool | list[list[bool]] | ArrayLike, optional): Whether
            cells are disabled. A scalar bool is broadcast to all cells; a
            nested list or numpy bool array sets a per-element mask.
            Defaults to False.
        symmetric (bool, optional): If True, editing cell `[i][j]` also
            updates cell `[j][i]`. Requires a square matrix. Defaults to False.
        scientific (bool, optional): If True, display values in scientific
            notation (e.g., `1.0e-4`). Defaults to False.
        precision (int | None, optional): Number of decimal places
            displayed. When None, inferred from the data values and step
            sizes. Defaults to None.
        row_labels (list[str] | None, optional): Labels for each row.
            Defaults to None.
        column_labels (list[str] | None, optional): Labels for each column.
            Defaults to None.
        debounce (bool, optional): If True, value updates are only sent
            to the backend on mouse-up (pointer release) instead of on
            every drag movement. Useful when the matrix drives expensive
            downstream computations. Defaults to False.
        label (str, optional): Markdown/LaTeX label for the element.
            Defaults to "".
    """

    _name: Final[str] = "marimo-matrix"

    def __init__(
        self,
        value: list[list[Numeric]] | ArrayLike,
        *,
        min_value: Numeric | list[list[Numeric]] | ArrayLike | None = None,
        max_value: Numeric | list[list[Numeric]] | ArrayLike | None = None,
        step: Numeric | list[list[Numeric]] | ArrayLike = 1.0,
        disabled: bool | list[list[bool]] | ArrayLike = False,
        symmetric: bool = False,
        scientific: bool = False,
        precision: int | None = None,
        row_labels: list[str] | None = None,
        column_labels: list[str] | None = None,
        debounce: bool = False,
        label: str = "",
    ) -> None:
        # Convert and validate value
        data = _to_nested_list(value)
        rows = len(data)
        cols = len(data[0])

        # Broadcast params to full matrices
        min_val = (
            _broadcast("min_value", min_value, rows, cols)
            if min_value is not None
            else None
        )
        max_val = (
            _broadcast("max_value", max_value, rows, cols)
            if max_value is not None
            else None
        )
        step_val = _broadcast("step", step, rows, cols)
        disabled_val = _broadcast("disabled", disabled, rows, cols)

        args = _validate_and_build_args(
            data,
            min_val=min_val,
            max_val=max_val,
            step_val=step_val,
            disabled_val=disabled_val,
            symmetric=symmetric,
            scientific=scientific,
            precision=precision,
            row_labels=row_labels,
            column_labels=column_labels,
            debounce=debounce,
        )

        super().__init__(
            component_name=matrix._name,
            initial_value=data,
            label=label,
            args=args,
            on_change=None,
        )

    def _convert_value(
        self, value: list[list[Numeric]]
    ) -> list[list[Numeric]]:
        return value
