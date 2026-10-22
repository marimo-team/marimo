# Copyright 2026 Marimo. All rights reserved.
"""Edge computation logic for cell dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.cell import CellImpl
    from marimo._ast.visitor import Name
    from marimo._runtime.dataflow.definitions import DefinitionRegistry
    from marimo._runtime.dataflow.topology import (
        GraphTopology,
        MutableGraphTopology,
    )
    from marimo._types.ids import CellId_t

from marimo._ast.sql_visitor import SQLRef, SQLTypes
from marimo._runtime.dataflow.definitions import effective_variable_definitions

LOGGER = _loggers.marimo_logger()


def register_cell_dependencies(
    cell_id: CellId_t,
    cell: CellImpl,
    topology: MutableGraphTopology,
    definitions: DefinitionRegistry,
) -> tuple[set[CellId_t], set[CellId_t]]:
    """Add a compiled cell to the dependency indexes and resolve its edges.

    The caller applies the returned parent/child edges. Cell runtime state
    is never modified.
    """
    topology.add_node(cell_id, cell)
    # Definitions must be indexed before resolving references to this cell.
    for name, variable_data in cell.variable_data.items():
        definitions.register_definition(cell_id, name, variable_data)
    return compute_edges_for_cell(cell_id, cell, topology, definitions)


def _cell_references(
    cell: CellImpl, *, namespace_only: bool = False
) -> Iterator[tuple[Name, SQLRef | None]]:
    if not namespace_only:
        for name in cell.refs:
            yield name, cell.sql_refs.get(name)
    for ref in cell.sql_namespace_refs:
        yield ref.qualified_name, ref


def _matches_reference(
    cell: CellImpl,
    reference_name: Name,
    sql_ref: SQLRef | None,
    *,
    definition_name: Name,
    language: Literal["python", "sql"],
    sql_definition: SQLRef | None,
    sql_kind: SQLTypes,
    catalogs: frozenset[str],
) -> bool:
    if language == "python":
        return reference_name == definition_name and (
            sql_ref is None or sql_ref.kind != "schema"
        )
    if cell.language != "sql":
        return False
    if sql_ref is None:
        return reference_name == definition_name
    definition = sql_definition or SQLRef.from_qualified_name(definition_name)
    return sql_ref.matches_hierarchical_ref(
        definition_name, definition, sql_kind, catalogs=catalogs
    )


def get_referring_cells(
    name: Name,
    language: Literal["python", "sql"],
    topology: GraphTopology,
    sql_definition: SQLRef | None = None,
    sql_kind: SQLTypes = "any",
    catalogs: frozenset[str] = frozenset(),
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

            for ref, sql_ref in _cell_references(cell):
                if _matches_reference(
                    cell,
                    ref,
                    sql_ref,
                    definition_name=name,
                    language=language,
                    sql_definition=sql_definition,
                    sql_kind=sql_kind,
                    catalogs=catalogs,
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


def resolve_cell_references(
    cell_id: CellId_t,
    cell: CellImpl,
    topology: GraphTopology,
    definitions: DefinitionRegistry,
    *,
    namespace_only: bool = False,
) -> dict[Name, set[CellId_t]]:
    """Resolve each reference to its defining cells using language semantics.

    Keys retain the reference as written, including SQL qualification.
    Unresolved names and references to the cell itself are excluded.
    """
    resolved: dict[Name, set[CellId_t]] = {}
    catalogs = (
        definitions.sql_catalogs if cell.language == "sql" else frozenset()
    )
    for name, sql_ref in _cell_references(cell, namespace_only=namespace_only):
        candidates: dict[CellId_t, set[Name]] = {
            cid: {name}
            for cid in definitions.get_defining_cells(name) - {cell_id}
        }
        if sql_ref is not None:
            for (
                cell_ids,
                variable_name,
            ) in definitions.find_sql_hierarchical_matches(sql_ref):
                for cid in cell_ids - {cell_id}:
                    candidates.setdefault(cid, set()).add(variable_name)

        for other_id, names in candidates.items():
            if not _is_valid_cell_reference(other_id, name, topology):
                continue
            other_cell = topology.cells[other_id]
            if any(
                _matches_reference(
                    cell,
                    name,
                    sql_ref,
                    definition_name=variable_name,
                    language=variable.language,
                    sql_definition=variable.sql_ref,
                    sql_kind=cast(SQLTypes, variable.kind),
                    catalogs=catalogs,
                )
                for variable_name in names
                for variable in effective_variable_definitions(
                    other_cell.variable_data[variable_name]
                )
            ):
                resolved.setdefault(name, set()).add(other_id)

    return resolved


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
    catalogs = (
        definitions.sql_catalogs if cell.language == "sql" else frozenset()
    )

    # First, process the variables that this cell defines. Any cell
    # that refers to a defined variable becomes a child of this cell.
    for name, variable_data in cell.variable_data.items():
        variables = effective_variable_definitions(variable_data)
        for variable in variables:
            referring_cells = get_referring_cells(
                name,
                language=variable.language,
                topology=topology,
                sql_definition=variable.sql_ref,
                sql_kind=cast(SQLTypes, variable.kind),
                catalogs=catalogs,
            ) - {cell_id}
            children.update(referring_cells)

    for defining_cells in resolve_cell_references(
        cell_id, cell, topology, definitions
    ).values():
        parents.update(defining_cells)

    # Next, process the cells references. The cell becomes a child
    # of cells that define its referenced variables. We also have
    # special logic for handling references that are deleted by this cell,
    # since cells that delete variables that were defined elsewhere
    # are made children of cells that reference that variable.
    for name in cell.refs:
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
