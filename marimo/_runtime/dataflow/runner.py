# Copyright 2026 Marimo. All rights reserved.
"""Runner utility for executing individual cells in a graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._runtime.executor import ExecutionConfig, get_executor

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.dataflow.graph import DirectedGraph
    from marimo._types.ids import CellId_t


class Runner:
    """Utility for running individual cells in a graph

    This class provides methods to a run a cell in the graph and obtain its
    output (last expression) and the values of its defs.

    If needed, the runner will recursively compute the values of the cell's
    refs by executing its ancestors. Refs can also be substituted by the
    caller.

    TODO(akshayka): Add an API for caching defs across cell runs.
    """

    def __init__(self, graph: DirectedGraph) -> None:
        self._graph = graph
        self._executor = get_executor(ExecutionConfig())

    @staticmethod
    def _returns(cell_impl: CellImpl, glbls: dict[str, Any]) -> dict[str, Any]:
        return {name: glbls[name] for name in cell_impl.defs if name in glbls}

    @staticmethod
    def _substitute_refs(
        cell_impl: CellImpl,
        glbls: dict[str, Any],
        kwargs: dict[str, Any],
    ) -> None:
        for argname, argvalue in kwargs.items():
            if argname in cell_impl.refs:
                glbls[argname] = argvalue
            else:
                raise ValueError(
                    f"Cell got unexpected argument {argname}"
                    f"The allowed arguments are {cell_impl.refs}."
                )

    def _get_ancestors(
        self, cell_impl: CellImpl, kwargs: dict[str, Any]
    ) -> set[CellId_t]:
        from marimo._runtime.dataflow import transitive_closure

        # Get the transitive closure of parents defining unsubstituted refs
        graph = self._graph
        substitutions = set(kwargs.keys())
        unsubstituted_refs = cell_impl.refs - substitutions
        parent_ids = set(
            [
                parent_id
                for parent_id in graph.parents[cell_impl.cell_id]
                if graph.cells[parent_id].defs.intersection(unsubstituted_refs)
            ]
        )
        return transitive_closure(graph, parent_ids, children=False)

    @staticmethod
    def _validate_kwargs(cell_impl: CellImpl, kwargs: dict[str, Any]) -> None:
        for argname in kwargs:
            if argname not in cell_impl.refs:
                raise ValueError(
                    f"Cell got unexpected argument {argname}; "
                    f"The allowed arguments are {cell_impl.refs}."
                )

    def is_coroutine(self, cell_id: CellId_t) -> bool:
        return self._graph.cells[cell_id].is_coroutine() or any(
            self._graph.cells[cid].is_coroutine()
            for cid in self._get_ancestors(
                self._graph.cells[cell_id], kwargs={}
            )
        )

    async def run_cell_async(
        self, cell_id: CellId_t, kwargs: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        """Run a possibly async cell and its ancestors

        Substitutes kwargs as refs for the cell, omitting ancestors that
        whose refs are substituted.
        """
        from marimo._runtime.dataflow import topological_sort

        graph = self._graph
        cell_impl = graph.cells[cell_id]
        Runner._validate_kwargs(cell_impl, kwargs)
        ancestor_ids = self._get_ancestors(cell_impl, kwargs)

        glbls: dict[str, Any] = {}
        for cid in topological_sort(graph, ancestor_ids):
            await self._executor.execute_cell_async(
                graph.cells[cid], glbls, graph
            )

        Runner._substitute_refs(cell_impl, glbls, kwargs)
        output = await self._executor.execute_cell_async(
            graph.cells[cell_impl.cell_id], glbls, graph
        )
        defs = Runner._returns(cell_impl, glbls)
        return output, defs

    def run_cell_sync(
        self, cell_id: CellId_t, kwargs: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        """Run a synchronous cell and its ancestors

        Substitutes kwargs as refs for the cell, omitting ancestors that
        whose refs are substituted.

        Raises a `RuntimeError` if the cell or any of its unsubstituted
        ancestors are coroutine functions.
        """
        from marimo._runtime.dataflow import topological_sort

        graph = self._graph
        cell_impl = graph.cells[cell_id]
        if cell_impl.is_coroutine():
            raise RuntimeError(
                "A coroutine function can't be run synchronously. "
                "Use `run_async()` instead"
            )

        Runner._validate_kwargs(cell_impl, kwargs)
        ancestor_ids = self._get_ancestors(cell_impl, kwargs)

        if any(graph.cells[cid].is_coroutine() for cid in ancestor_ids):
            raise RuntimeError(
                "Cell has an ancestor that is a "
                "coroutine (async) cell. Use `run_async()` instead"
            )

        glbls: dict[str, Any] = {}
        for cid in topological_sort(graph, ancestor_ids):
            self._executor.execute_cell(graph.cells[cid], glbls, graph)

        self._substitute_refs(cell_impl, glbls, kwargs)
        output = self._executor.execute_cell(
            graph.cells[cell_impl.cell_id], glbls, graph
        )
        defs = Runner._returns(cell_impl, glbls)
        return output, defs
