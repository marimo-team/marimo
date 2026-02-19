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
from marimo._plugins.ui._impl.matrix import (
    Numeric,
    _broadcast,
    _validate_and_build_args,
)

if TYPE_CHECKING:
    from numpy.typing import ArrayLike


def _to_flat_list(
    value: list[Numeric] | ArrayLike,
) -> list[Numeric]:
    """Validate and convert input to a flat list of numbers.

    Accepts a flat list of numbers or a 1D array-like with ``.tolist()``.
    Rejects empty, non-1D, or nested inputs.
    """
    if hasattr(value, "tolist"):
        value = value.tolist()

    if not isinstance(value, list):
        raise ValueError(
            f"`value` must be a list or 1D array-like, got {type(value)}"
        )

    if not value:
        raise ValueError("`value` must be non-empty")

    for i, v in enumerate(value):
        if isinstance(v, (list, tuple)):
            raise ValueError(
                f"`value` must be 1D, but element {i} is a {type(v).__name__}"
            )

    return value


def _1d_to_2d(
    name: str,
    param: Any,
    transpose: bool,
) -> Any:
    """Convert a 1D list param to 2D for matrix consumption.

    Scalars pass through unchanged (they'll be broadcast by ``_broadcast``).
    A 1D list becomes ``[[v] for v in param]`` (column) or ``[param]`` (row).
    """
    if hasattr(param, "tolist"):
        param = param.tolist()

    if not isinstance(param, list):
        # Scalar — let _broadcast handle it
        return param

    # Must be a flat list at this point
    for i, v in enumerate(param):
        if isinstance(v, (list, tuple)):
            raise ValueError(
                f"`{name}` must be scalar or 1D, "
                f"but element {i} is a {type(v).__name__}"
            )

    if transpose:
        return [param]
    else:
        return [[v] for v in param]


@mddoc
class vector(UIElement[list[list[Numeric]], list[Numeric]]):
    """An interactive vector editor.

    A convenience wrapper around ``mo.ui.matrix`` for 1D data. Each
    entry is a drag-slider. By default the vector is displayed as a
    column; pass ``transpose=True`` for a row layout.

    Examples:
        ```python
        v = mo.ui.vector([1, 2, 3])
        ```

        ```python
        v = mo.ui.vector([0, 0, 0], min_value=-10, max_value=10, step=0.5)
        ```

        ```python
        # Row vector
        v = mo.ui.vector([1, 2, 3], transpose=True)
        ```

        ```python
        import numpy as np

        v = mo.ui.vector(np.zeros(5), step=0.1)
        ```

    Attributes:
        value (list[Numeric]): The current 1D vector as a flat list.
            Use ``np.asarray(vector.value)`` to convert to a numpy array.

    Args:
        value (list[Numeric] | ArrayLike): Initial 1D vector data.
            Accepts a flat list of numbers or a 1D numpy array.
        transpose (bool, optional): If True, display as a row vector
            instead of a column vector. Defaults to False.
        entry_labels (list[str] | None, optional): Labels for each
            entry. Mapped to row labels (column vector) or column
            labels (row vector). Defaults to None.
        min_value (Numeric | list[Numeric] | ArrayLike | None, optional):
            Minimum allowed value. A scalar is broadcast to all entries;
            a list sets per-entry bounds. Defaults to None.
        max_value (Numeric | list[Numeric] | ArrayLike | None, optional):
            Maximum allowed value. A scalar is broadcast to all entries;
            a list sets per-entry bounds. Defaults to None.
        step (Numeric | list[Numeric] | ArrayLike, optional): Drag
            increment. A scalar is broadcast; a list sets per-entry
            steps. Defaults to 1.0.
        disabled (bool | list[bool] | ArrayLike, optional): Whether
            entries are disabled. A scalar is broadcast; a list sets
            a per-entry mask. Defaults to False.
        scientific (bool, optional): If True, display values in
            scientific notation. Defaults to False.
        precision (int | None, optional): Number of decimal places
            displayed. When None, inferred from the data values and step
            sizes. Defaults to None.
        debounce (bool, optional): If True, value updates are only
            sent on pointer release. Defaults to False.
        label (str, optional): Markdown/LaTeX label. Defaults to "".
        on_change (Callable | None, optional): Optional callback to
            run when this element's value changes.
    """

    _name: Final[str] = "marimo-matrix"

    def __init__(
        self,
        value: list[Numeric] | ArrayLike,
        *,
        transpose: bool = False,
        entry_labels: list[str] | None = None,
        min_value: Numeric | list[Numeric] | ArrayLike | None = None,
        max_value: Numeric | list[Numeric] | ArrayLike | None = None,
        step: Numeric | list[Numeric] | ArrayLike = 1.0,
        disabled: bool | list[bool] | ArrayLike = False,
        scientific: bool = False,
        precision: int | None = None,
        debounce: bool = False,
        label: str = "",
        on_change: Callable[[list[Numeric]], None] | None = None,
    ) -> None:
        flat = _to_flat_list(value)

        # Convert 1D value → 2D for matrix plugin
        if transpose:
            data: list[list[Numeric]] = [flat]
        else:
            data = [[v] for v in flat]

        rows = len(data)
        cols = len(data[0])

        # Convert 1D params → 2D
        min_2d = _1d_to_2d("min_value", min_value, transpose)
        max_2d = _1d_to_2d("max_value", max_value, transpose)
        step_2d = _1d_to_2d("step", step, transpose)
        disabled_2d = _1d_to_2d("disabled", disabled, transpose)

        # Broadcast to full matrix shape
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

        # Map entry_labels to row_labels or column_labels
        if transpose:
            row_labels = None
            column_labels = entry_labels
        else:
            row_labels = entry_labels
            column_labels = None

        args = _validate_and_build_args(
            data,
            min_val=min_val,
            max_val=max_val,
            step_val=step_val,
            disabled_val=disabled_val,
            symmetric=False,
            scientific=scientific,
            precision=precision,
            row_labels=row_labels,
            column_labels=column_labels,
            debounce=debounce,
        )

        super().__init__(
            component_name=vector._name,
            initial_value=data,
            label=label,
            args=args,
            on_change=on_change,
        )

    def _convert_value(
        self, value: list[list[Numeric]]
    ) -> list[Numeric]:
        return [cell for row in value for cell in row]
