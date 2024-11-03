from marimo._ast.visitor import VariableData
from marimo._data.get_datasets import get_table_manager_or_none
from marimo._output.rich_help import mddoc
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)


@mddoc
def register_datasource(obj: object, name: str) -> None:
    """Register a datasource with the current context.

    This datasource will be available to other cells in the same context.

    **Args:**

    - `obj`: The datasource object to register.
    - `name`: The name to register the datasource under.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return

    if get_table_manager_or_none(obj) is None:
        raise ValueError(f"Failed to get table data for variable {name}")

    ctx.globals[name] = obj

    cell_id = ctx.execution_context.cell_id
    cell = ctx.graph.cells[cell_id]
    cell.defs.add(name)
    cell.variable_data[name] = [VariableData("variable")]
    if name in ctx.graph.definitions:
        ctx.graph.definitions[name].append(cell_id)
    else:
        ctx.graph.definitions.update({name: [cell_id]})
