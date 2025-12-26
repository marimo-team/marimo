# Copyright 2026 Marimo. All rights reserved.
"""Edge computation logic for cell dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, cast

from marimo import _loggers

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.sql_visitor import SQLRef
    from marimo._ast.visitor import Name
    from marimo._runtime.dataflow.definitions import DefinitionRegistry
    from marimo._runtime.dataflow.topology import GraphTopology
    from marimo._types.ids import CellId_t

from marimo._ast.sql_visitor import SQLTypes

LOGGER = _loggers.marimo_logger()


def get_referring_cells(
    name: Name,
    language: Literal["python", "sql"],
    topology: GraphTopology,
) -> set[CellId_t]:
    """Get all cells that have a ref to `name`.

    The variable can be either a Python variable or a SQL variable (table).
    SQL variables don't leak to Python cells, but Python variables do leak
    to SQL.

    Only does a local analysis of refs, without taking into consideration
    whether refs are defined by other cells.
    """
    if language == "sql":
        # For SQL, only return SQL cells that reference the name
        cells = set()
        for cid, cell in topology.cells.items():
            if cell.language != "sql":
                continue

            for ref in cell.refs:
                # Direct reference match
                if ref == name:
                    cells.add(cid)
                    break

                sql_ref = cell.sql_refs.get(ref)

                kind: SQLTypes = "any"
                if name in cell.variable_data:
                    variable_data = cell.variable_data[name][-1]
                    kind = cast(SQLTypes, variable_data.kind)

                # Hierarchical reference match
                if sql_ref and sql_ref.matches_hierarchical_ref(
                    name, ref, kind
                ):
                    cells.add(cid)
                    break

        return cells
    else:
        # For Python, return all cells that reference the name
        return {
            cid for cid, cell in topology.cells.items() if name in cell.refs
        }


def _is_valid_cell_reference(
    cell_id: CellId_t, variable_name: Name, topology: GraphTopology
) -> bool:
    """Check if a cell reference is valid and log errors if not."""
    if cell_id not in topology.cells:
        LOGGER.error(
            "Variable %s is defined in cell %s, but is not in the graph",
            variable_name,
            cell_id,
        )
        return False
    return True


def _resolve_variable_name(
    name: Name,
    other_cell: CellImpl,
    sql_ref: Optional[SQLRef],
    sql_matches: list[tuple[set[CellId_t], Name]],
) -> Name:
    """Resolve the variable name to use when checking if it exists in another cell.

    For regular (non-SQL) references, returns the original name unchanged.
    For SQL hierarchical references, finds the variable name from sql_matches that
    is actually defined in the other_cell.

    Example:
        cell_1: CREATE SCHEMA schema_name
        cell_2: CREATE TABLE schema_name.table_name
        cell_3: FROM schema_name.table_name SELECT *

        When cell_3 references "schema_name.table_name":
        - For cell_1: returns "schema_name" (what cell_1 actually defines)
        - For cell_2: returns "table_name" (what cell_2 actually defines)
    """
    if not sql_ref or name in other_cell.variable_data:
        return name

    # For SQL hierarchical references, find the matching variable name
    for _, matching_variable_name in sql_matches:
        if matching_variable_name in other_cell.variable_data:
            return matching_variable_name

    return name


def compute_edges_for_cell(
    cell_id: CellId_t,
    cell: CellImpl,
    topology: GraphTopology,
    definitions: DefinitionRegistry,
) -> tuple[set[CellId_t], set[CellId_t]]:
    """Compute parent and child edges for a cell being registered.

    Args:
        cell_id: The ID this cell is being registered with
        cell: The cell to compute edges for
        topology: The graph topology
        definitions: The definition registry

    Returns:
        Tuple of (parents, children) where:
        - parents: cells that this cell depends on
        - children: cells that depend on this cell
    """
    parents: set[CellId_t] = set()
    children: set[CellId_t] = set()

    # First, process the variables that this cell defines. Any cell
    # that refers to a defined variable becomes a child of this cell.
    for name, variable_data in cell.variable_data.items():
        # NB. Only the last definition matters.
        # Technically more nuanced with branching statements, but this is
        # the best we can do with static analysis.
        variable = variable_data[-1]

        # a cell can refer to its own defs, but that doesn't add an
        # edge to the dependency graph
        referring_cells = get_referring_cells(
            name,
            language=variable.language,
            topology=topology,
        ) - {cell_id}

        children.update(referring_cells)

    # Next, process the cells references. The cell becomes a child
    # of cells that define its referenced variables. We also have
    # special logic for handling references that are deleted by this cell,
    # since cells that delete variables that were defined elsewhere
    # are made children of cells that reference that variable.
    for name in cell.refs:
        # First, for each referenced variable, we add cells that define
        # that variable as parents
        other_ids_defining_name: set[CellId_t] = definitions.definitions.get(
            name, set()
        ) - {cell_id}

        variable_name: Name = name

        # Handle SQL matching for hierarchical references
        sql_matches: list[tuple[set[CellId_t], Name]] = []
        sql_ref = cell.sql_refs.get(name)
        if sql_ref:
            sql_matches = definitions.find_sql_hierarchical_matches(sql_ref)
            for matching_cell_ids, _ in sql_matches:
                if cell_id in matching_cell_ids:
                    LOGGER.debug("Cell %s is referencing itself", cell_id)
                    continue
                other_ids_defining_name.update(matching_cell_ids)

        # If other_ids_defining_name is empty, the user will get a
        # NameError at runtime (unless the symbol is a builtin).
        for other_id in other_ids_defining_name:
            if other_id == cell_id:
                LOGGER.error("Cell %s is referencing itself", cell_id)
                continue
            if not _is_valid_cell_reference(other_id, variable_name, topology):
                continue
            other_cell = topology.cells[other_id]

            variable_name = _resolve_variable_name(
                variable_name, other_cell, sql_ref, sql_matches
            )

            # If we don't have a matching variable name, skip
            if variable_name not in other_cell.variable_data:
                LOGGER.error(
                    "Variable %s is not defined in cell %s",
                    variable_name,
                    other_id,
                )
                continue

            other_variable_data = other_cell.variable_data[variable_name][-1]
            language = other_variable_data.language
            if language == "sql" and cell.language == "python":
                # SQL table/db def -> Python ref is not an edge
                continue
            if language == "sql" and cell.language == "sql":
                # Edges between SQL cells need to respect hierarchy.
                if sql_ref and not sql_ref.matches_hierarchical_ref(
                    variable_name,
                    other_variable_data.qualified_name or name,
                    kind=cast(SQLTypes, other_variable_data.kind),
                ):
                    continue
            parents.add(other_id)

        # Next, any cell that deletes this referenced variable is made
        # a child of this cell. In particular, if a cell deletes a
        # variable, it becomes a child of all other cells that
        # reference that variable. This means that if two cells delete
        # the same variable, they form a cycle.
        #
        # For example, two cells
        #
        #   cell u: x
        #   cell v: del x
        #
        # v becomes a child of u.
        #
        # Another example:
        #
        #   cell u: del x
        #   cell v: del x
        #
        # u and v form a cycle.
        other_ids_deleting_name: set[CellId_t] = {
            cid
            for cid in get_referring_cells(
                name, language="python", topology=topology
            )
            if name in topology.cells[cid].deleted_refs
        } - {cell_id}
        children.update(other_ids_deleting_name)

    # Finally, if this cell deletes a variable, we make it a child of
    # all other cells that reference this variable.
    for name in cell.deleted_refs:
        referring_cells = get_referring_cells(
            name, language="python", topology=topology
        ) - {cell_id}
        parents.update(referring_cells)

    return parents, children
