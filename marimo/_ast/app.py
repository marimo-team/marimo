# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import builtins
import itertools
import textwrap
from collections.abc import Sequence
from typing import Any, Optional

from marimo._ast.cell import (
    CellFunction,
    CellId_t,
    cell_factory,
    cell_func_t,
    execute_cell,
)
from marimo._ast.errors import (
    CycleError,
    DeleteNonlocalError,
    MultipleDefinitionError,
    UnparsableError,
)
from marimo._output.rich_help import mddoc
from marimo._runtime.dataflow import DirectedGraph, topological_sort


@mddoc
class App:
    """A marimo app.

    A marimo app is a dataflow graph, with each node computing a Python
    function.

    This class has no public API, but this may change in the future.
    """

    def __init__(self) -> None:
        # cell is unparsable <=> its value in self._cell_functions is None
        self._cell_functions: dict[CellId_t, Optional[CellFunction]] = {}
        self._cell_names: dict[CellId_t, str] = {}
        self._codes: dict[CellId_t, str] = {}
        self._registration_order: list[CellId_t] = []

        self._cell_id_counter = 0
        self._unparsable = False
        self._initialized = False

    def _create_cell_id(
        self, cell_function: Optional[CellFunction]
    ) -> CellId_t:
        del cell_function
        cell_id = str(self._cell_id_counter)
        self._registration_order.append(cell_id)
        self._cell_id_counter += 1
        return str(cell_id)

    def cell(self, f: cell_func_t) -> CellFunction:
        cell_function = cell_factory(f)
        cell_id = self._create_cell_id(cell_function)
        self._cell_functions[cell_id] = cell_function
        self._cell_names[cell_id] = f.__name__
        self._codes[cell_id] = cell_function.cell.code
        return cell_function

    def _validate_args(self) -> None:
        """Validate the args of each cell function.

        Args should match cell.refs, excluding builtins that haven't been
        shadowed by other cells.

        This function must be called after all cells have been parsed, because
        it's only then that we know the set of unshadowed builtins.

        Raises: ValueError if a cell has an invalid arg set.
        """
        defs = set(
            itertools.chain.from_iterable(
                f.cell.defs
                for f in self._cell_functions.values()
                if f is not None
            )
        )
        unshadowed_builtins = set(builtins.__dict__.keys()).difference(defs)
        for f in self._cell_functions.values():
            if f is None:
                continue
            expected_args = f.cell.refs - unshadowed_builtins
            if f.args != expected_args:
                suggested_sig = (
                    f"def {f.__name__}({', '.join(sorted(expected_args))}):"
                )
                raise ValueError(
                    "A cell must take all its refs as args. "
                    "This rule is violated by the following function:\n\n"
                    + textwrap.indent(f.code, prefix="    ")
                    + "\n"
                    f"Fix: Make '{suggested_sig}' this function's signature."
                )

    def _unparsable_cell(self, code: str, name: Optional[str] = None) -> None:
        cell_id = self._create_cell_id(None)
        self._cell_names[cell_id] = name if name is not None else "__"
        # - code.split("\n")[1:-1] disregards first and last lines, which are
        #   empty
        # - line[4:] removes leading indent in multiline string
        # - replace(...) unescapes double quotes
        # - rstrip() removes an extra newline
        code = "\n".join(
            [line[4:].replace('\\"', '"') for line in code.split("\n")[1:-1]]
        )
        self._codes[cell_id] = code
        self._unparsable = True

    def _maybe_initialize(self) -> None:
        assert not self._unparsable
        if not self._initialized:
            # ids of cells to add to the graph, in the order that they
            # were registered with the app
            self._cell_ids = [
                # exclude unparseable cells from graph
                cid
                for cid, f in self._cell_functions.items()
                if f is not None
            ]
            self._graph = DirectedGraph()
            for cell_id in self._cell_ids:
                cell_function = self._cell_functions[cell_id]
                assert cell_function is not None
                self._graph.register_cell(cell_id, cell_function.cell)
            self._defs = self._graph.definitions.keys()

            # these two helper functions could be written as concise
            # `any` expressions using assignment expressions, but
            # that's a silly reason to make Python < 3.8 incompatible
            # with marimo.
            def get_multiply_defined() -> Optional[str]:
                for name, definers in self._graph.definitions.items():
                    if len(definers) > 1:
                        return name
                return None

            def get_deleted_nonlocal_ref() -> Optional[str]:
                for cell in self._graph.cells.values():
                    for ref in cell.deleted_refs:
                        if ref in self._graph.definitions:
                            return ref
                return None

            try:
                if self._graph.cycles:
                    raise CycleError(
                        "This app can't be run because it has cycles."
                    )
                name = get_multiply_defined()
                if name is not None:
                    raise MultipleDefinitionError(
                        "This app can't be run because it has multiple "
                        f"definitions of the name {name}"
                    )
                ref = get_deleted_nonlocal_ref()
                if ref is not None:
                    raise DeleteNonlocalError(
                        "This app can't be run because at least one cell "
                        f"deletes one of its refs (the ref's name is {ref})"
                    )
                self._execution_order = topological_sort(
                    self._graph, self._cell_ids
                )
            finally:
                self._initialized = True

    def run(self) -> tuple[Sequence[Any], dict[str, Any]]:
        if self._unparsable:
            raise UnparsableError(
                "This app can't be run because it has unparsable cells."
            )

        self._maybe_initialize()
        glbls: dict[Any, Any] = {}
        outputs = {
            cid: execute_cell(cell_function.cell, glbls)
            for cid in self._execution_order
            if (cell_function := self._cell_functions[cid]) is not None
        }
        # Return
        # - the outputs, sorted in the order that cells were added to the
        #   graph
        # - dict of defs -> values
        return (
            tuple(
                outputs[cid]
                for cid in self._registration_order
                # exclude unparseable cells
                if cid in outputs
            ),
            {name: glbls[name] for name in self._defs},
        )
