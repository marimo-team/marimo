# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._plugins.stateless.flex import vstack
from marimo._plugins.ui._impl.input import code_editor
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError


def substitute_show_code_with_arg(code: str) -> str:
    pattern = r"mo\.show_code\((.*)\)"
    return re.sub(pattern, r"\1", code, flags=re.DOTALL).strip()


def show_code(output: object = None) -> Html:
    """Display an output along with the code of the current cell.

    Use `mo.show_code` to show the code of the current cell along with
    the cell's output. This is useful if you want a cell's code to
    appear in the app preview or when running the notebook as an app
    with `marimo run`.

    In the displayed code, all occurrences of mo.show_code(...) will be
    replaced with ...

    Show code that produces the output `factorial(5)`:

    ```python
    def factorial(n: int) -> int:
        if n == 0:
            return 1
        return n * factorial(n - 1)


    mo.show_code(factorial(5))
    ```

    Show code of a cell, without an output:

    ```python
    def factorial(n: int) -> int:
        if n == 0:
            return 1
        return n * factorial(n - 1)


    mo.show_code()
    ```

    **Args:**

    - output: the output to display above the cell's code; omit the output
      to just show the cel's code, without an output.

    **Returns:**

    HTML of the `output` arg displayed with its code.
    """
    try:
        context = get_context()
    except ContextNotInitializedError:
        return as_html(output)

    cell_id = context.cell_id
    if cell_id is None:
        return as_html(output)

    cell = context.graph.cells[cell_id]
    code = substitute_show_code_with_arg(cell.code)

    if output is not None:
        return vstack(
            [
                code_editor(value=code, disabled=True, min_height=1),
                as_html(output),
            ]
        )
    else:
        return code_editor(value=code, disabled=True, min_height=1)
