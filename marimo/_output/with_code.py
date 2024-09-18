from __future__ import annotations
import ast

from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError


class ReplaceWithCodeCalls(ast.NodeTransformer):

    def visit_Call(self, node: ast.Call) -> ast.Expression | ast.Call:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "mo"
            and node.func.attr == "with_code"
            and len(node.args) > 0
        ):
            return ast.Expression(node.args[0])
        return node


def with_code(output: object) -> Html:
    try:
        context = get_context()
    except ContextNotInitializedError:
        return as_html(output)

    cell_id = context.cell_id
    if cell_id is None:
        return as_html(output)

    cell = context.graph.cells[cell_id]
    try:
        tree = ast.parse(cell.code)
    except Exception:
        return as_html(output)

    transformed = ReplaceWithCodeCalls().visit(tree)
    return md(
        f"""
{as_html(output)}

```python
{cell.code}
```
"""
    )
