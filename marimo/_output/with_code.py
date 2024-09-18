from __future__ import annotations
import re

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError
from marimo._plugins.ui._impl.input import code_editor


def with_code(output: object = None) -> Html:
    """Display an output above the code of the current cell.

    Use `mo.with_code` to show the code of the current cell below
    the cell's output. This is useful if you want a cell's code to
    appear in the app preview or when running the notebook as an app
    with `marimo run`.

    In the displayed code, all occurrences of mo.with_code(...) will be
    replaced with ...

    Show code that produces the output `factorial(5)`:

    ```python
    def factorial(n: int) -> int:
        if n == 0:
            return 1
        return n * factorial(n - 1)

    mo.with_code(factorial(5))
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

    HTML of the `output` arg with its code displayed below it.
    """
    try:
        context = get_context()
    except ContextNotInitializedError:
        return as_html(output)

    cell_id = context.cell_id
    if cell_id is None:
        return as_html(output)

    cell = context.graph.cells[cell_id]
    pattern = r"mo\.with_code\((.*?)\)"
    code = re.sub(pattern, r"\1", cell.code, flags=re.DOTALL).strip()

    if output is not None:
        return md(
            f"""
{as_html(output)}

{code_editor(value=code, disabled=True, min_height=1)}
"""
        )
    else:
        return code_editor(value=code, disabled=True, min_height=1)
