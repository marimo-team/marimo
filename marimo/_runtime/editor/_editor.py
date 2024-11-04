# Copyright 2024 Marimo. All rights reserved.
from marimo._ast.visitor import VariableData
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)


@mddoc
def register_datasource(obj: object, name: str) -> None:
    """Register a datasource.

    This registered object will be available in the global scope of the
    notebook, including as a variable in the graph.

    WARNING: This function may cause unintended bugs in reactivity, since
    defined variables cannot be statically analyzed. Also, this can be
    confusing for users if used inappropriately to flood the global scope.
    Please be mindful of this function.

    **Args:**

    - `obj`: The datasource object to register.
    - `name`: The name to register the datasource under.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if ctx.execution_context is None:
        return

    if get_table_manager_or_none(obj) is None:
        raise ValueError(f"Failed to get table data for variable {name}")

    ctx.globals[name] = obj

    cell_id = ctx.execution_context.cell_id
    cell = ctx.graph.cells[cell_id]
    cell.defs.add(name)
    cell.variable_data[name] = [VariableData("variable")]
    if name in ctx.graph.definitions:
        ctx.graph.definitions[name].add(cell_id)
    else:
        ctx.graph.definitions.update({name: {cell_id}})
