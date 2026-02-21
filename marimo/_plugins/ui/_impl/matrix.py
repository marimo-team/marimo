# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
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
            raise ValueError(  # noqa: TRY004
                f"`{name}` row {i} must be a list, got {type(row)}"
            )
        if len(row) != cols:
            raise ValueError(
                f"`{name}` row {i} has {len(row)} columns but expected {cols}"
            )
        for j, cell in enumerate(row):
            if isinstance(cell, (list, tuple)):
                raise ValueError(  # noqa: TRY004
                    f"`{name}` must be 2D, but found a nested "
                    f"sequence at position [{i}][{j}]"
                )
    return param


def _to_flat_list(
    value: list[Numeric] | ArrayLike,
) -> list[Numeric]:
    """Validate and convert input to a flat list of numbers.

    Accepts a flat list of numbers or a 1D array-like with `.tolist()`.
    Rejects empty, non-1D, or nested inputs.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list):
        raise ValueError(  # noqa: TRY004
            f"`value` must be a list or array-like, got {type(value)}"
        )

    if not value:
        raise ValueError("`value` must be non-empty")

    for i, v in enumerate(value):
        if isinstance(v, (list, tuple)):
            raise ValueError(  # noqa: TRY004
                f"`value` must be 1D, but element {i} is a {type(v).__name__}"
            )

    return value


def _1d_to_2d(
    name: str,
    param: Any,
) -> Any:
    """Convert a 1D list param to a column-vector 2D layout.

    Scalars pass through unchanged (they'll be broadcast by `_broadcast`).
    A 1D list `[a, b, c]` becomes `[[a], [b], [c]]`.
    """
    if hasattr(param, "tolist"):
        param = param.tolist()

    if not isinstance(param, list):
        # Scalar — let _broadcast handle it
        return param

    # Must be a flat list at this point
    for i, v in enumerate(param):
        if isinstance(v, (list, tuple)):
            raise ValueError(  # noqa: TRY004
                f"`{name}` must be scalar or 1D, "
                f"but element {i} is a {type(v).__name__}"
            )

    return [[v] for v in param]


def _parse_value(
    value: list[list[Numeric]] | list[Numeric] | ArrayLike,
) -> tuple[list[list[Numeric]], bool]:
    """Parse and validate initial matrix data.

    Returns `(data_2d, is_vector)` where *is_vector* is True when the
    input was a flat 1D list.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list):
        raise ValueError(  # noqa: TRY004
            f"`value` must be a list of lists or array-like, got {type(value)}"
        )

    if not value:
        raise ValueError("`value` must be non-empty")

    first = value[0]

    # 1D path
    if not isinstance(first, (list, tuple)):
        flat = _to_flat_list(value)
        return flat, True  # type: ignore[return-value]

    # 2D path
    if not first:
        raise ValueError(
            f"`value` must contain non-empty lists, but row 0 is {first!r}"
        )
    data_2d = _broadcast("value", value, len(value), len(first))
    return data_2d, False


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

    For example, `0.00153` -> `1.53e-3` -> 2 mantissa places,
    while `1e-8` -> `1e-8` -> 0 mantissa places.
    """
    if isinstance(x, int):
        # Strip trailing zeros: 1234000 -> 1.234e6 -> 3 places
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
    return min(best, 8)


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
            if (
                min_val is not None
                and max_val is not None
                and min_val[i][j] >= max_val[i][j]
            ):
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
class matrix(
    UIElement[list[list[Numeric]], list[list[Numeric]] | list[Numeric]]
):
    """An interactive matrix/vector editor.

    A matrix UI element in which each entry is a slider: click and drag
    horizontally on an entry to increment or decrement its value. The matrix
    can be configured in many ways, including element-wise bounds, element-wise
    steps, an element-wise disable mask, and symmetry enforcement. These
    configuration values may be any array-like object, including as lists,
    NumPy arrays, or torch Tensors.

    Supports both 2D (matrix) and 1D (vector) inputs. When a flat list is
    passed, the element displays as a column vector and `.value` returns a flat
    list.

    Examples:
        Basic 2D matrix:

        ```python
        mat = mo.ui.matrix([[1, 0], [0, 1]])
        mat
        ```

        Access the value in another cell with

        ```python
        mat.value  # [[1, 0], [0, 1]]
        ```

        Column vector (1D input):

        ```python
        v = mo.ui.matrix([1, 2, 3])
        v.value  # [1, 2, 3]
        ```

        Row vecto

        ```python
        v = mo.ui.matrix([[1, 2, 3]])
        v.value  # [[1, 2, 3]]
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
        value (list[list[Numeric]] | list[Numeric]): The current matrix
            as a nested list, or a flat list when created with 1D input.
            Use `np.asarray(matrix.value)` to convert to a numpy array.

    Args:
        value (list[list[Numeric]] | list[Numeric] | ArrayLike): Initial
            data. A nested list or 2D array creates a matrix; a flat list
            or 1D array creates a column vector. Rows and columns are
            inferred from the shape.
        min_value (Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike | None, optional):
            Minimum allowed value. A scalar is broadcast to all cells; a
            list or numpy array sets per-element bounds. For 1D input,
            accepts a flat list. None means unbounded. Defaults to None.
        max_value (Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike | None, optional):
            Maximum allowed value. A scalar is broadcast to all cells; a
            list or numpy array sets per-element bounds. For 1D input,
            accepts a flat list. None means unbounded. Defaults to None.
        step (Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike, optional):
            Drag increment. A scalar is broadcast to all cells; a list
            or numpy array sets per-element step sizes. For 1D input,
            accepts a flat list. Defaults to 1.0.
        disabled (bool | list[list[bool]] | list[bool] | ArrayLike, optional):
            Whether cells are disabled. A scalar bool is broadcast to all
            cells; a list or numpy bool array sets a per-element mask.
            For 1D input, accepts a flat list. Defaults to False.
        symmetric (bool, optional): If True, editing cell `[i][j]` also
            updates cell `[j][i]`. Requires a square matrix. Defaults to
            False.
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
        value: list[list[Numeric]] | list[Numeric] | ArrayLike,
        *,
        min_value: (
            Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike | None
        ) = None,
        max_value: (
            Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike | None
        ) = None,
        step: (
            Numeric | list[list[Numeric]] | list[Numeric] | ArrayLike
        ) = 1.0,
        disabled: bool | list[list[bool]] | list[bool] | ArrayLike = False,
        symmetric: bool = False,
        scientific: bool = False,
        precision: int | None = None,
        row_labels: list[str] | None = None,
        column_labels: list[str] | None = None,
        debounce: bool = False,
        label: str = "",
    ) -> None:
        parsed, is_vector = _parse_value(value)

        if is_vector:
            # --- 1D (vector) path: always a column vector ---
            flat: list[Numeric] = parsed  # type: ignore[assignment]

            if symmetric:
                raise ValueError(
                    "`symmetric` is not supported for 1D (vector) input"
                )

            data: list[list[Numeric]] = [[v] for v in flat]
            rows = len(data)
            cols = 1

            # Convert 1D params -> 2D column layout
            min_2d = _1d_to_2d("min_value", min_value)
            max_2d = _1d_to_2d("max_value", max_value)
            step_2d = _1d_to_2d("step", step)
            disabled_2d = _1d_to_2d("disabled", disabled)

            min_val = (
                _broadcast("min_value", min_2d, rows, cols)
                if min_value is not None
                else None
            )
            max_val = (
                _broadcast("max_value", max_2d, rows, cols)
                if max_value is not None
                else None
            )
            step_val = _broadcast("step", step_2d, rows, cols)
            disabled_val = _broadcast("disabled", disabled_2d, rows, cols)

        else:
            # --- 2D (matrix) path ---
            data = parsed  # type: ignore[assignment]
            rows = len(data)
            cols = len(data[0])

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

        self._is_vector = is_vector

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
    ) -> list[list[Numeric]] | list[Numeric]:
        if self._is_vector:
            return [cell for row in value for cell in row]
        return value
