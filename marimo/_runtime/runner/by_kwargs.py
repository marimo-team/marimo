# Copyright 2026 Marimo. All rights reserved.
"""Run individual cells in a graph with caller-provided ref substitution.

Backs the ``Cell.run(**kwargs)`` public API. Walks the cell's ancestor
closure (minus any ancestor whose defs the caller substituted via
kwargs), runs them with a fresh globals dict, then runs the target cell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._runtime.executor import (
    DefaultExecutor,
    Evaluator,
    EvaluatorConfig,
    build_evaluator,
)

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.dataflow.graph import DirectedGraph
    from marimo._runtime.runner.result import RunResult
    from marimo._types.ids import CellId_t


def _new_evaluator() -> Evaluator:
    """A fresh relaxed-mode Evaluator (no lifecycles)."""
    return build_evaluator(
        EvaluatorConfig(executor=DefaultExecutor(), lifecycles=[])
    )


def _returns(cell_impl: CellImpl, glbls: dict[str, Any]) -> dict[str, Any]:
    return {name: glbls[name] for name in cell_impl.defs if name in glbls}


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


def _validate_kwargs(cell_impl: CellImpl, kwargs: dict[str, Any]) -> None:
    for argname in kwargs:
        if argname not in cell_impl.refs:
            raise ValueError(
                f"Cell got unexpected argument {argname}; "
                f"The allowed arguments are {cell_impl.refs}."
            )


def _get_ancestors(
    graph: DirectedGraph,
    cell_impl: CellImpl,
    kwargs: dict[str, Any],
) -> set[CellId_t]:
    from marimo._runtime.dataflow import transitive_closure

    substitutions = set(kwargs.keys())
    unsubstituted_refs = cell_impl.refs - substitutions
    parent_ids = {
        parent_id
        for parent_id in graph.parents[cell_impl.cell_id]
        if graph.cells[parent_id].defs.intersection(unsubstituted_refs)
    }
    return transitive_closure(graph, parent_ids, children=False)


def _raise_on_exception(result: RunResult) -> None:
    if result.exception is not None and isinstance(
        result.exception, BaseException
    ):
        raise result.exception


def is_coroutine(graph: DirectedGraph, cell_id: CellId_t) -> bool:
    """True if the cell or any of its (unsubstituted) ancestors is async."""
    return graph.cells[cell_id].is_coroutine() or any(
        graph.cells[cid].is_coroutine()
        for cid in _get_ancestors(graph, graph.cells[cell_id], kwargs={})
    )


async def run_cell_async(
    graph: DirectedGraph,
    cell_id: CellId_t,
    kwargs: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Run a possibly async cell and its ancestors.

    Substitutes kwargs as refs for the cell, omitting ancestors whose
    refs are substituted.
    """
    from marimo._runtime.dataflow import topological_sort

    cell_impl = graph.cells[cell_id]
    _validate_kwargs(cell_impl, kwargs)
    ancestor_ids = _get_ancestors(graph, cell_impl, kwargs)

    evaluator = _new_evaluator()
    glbls: dict[str, Any] = {}
    for cid in topological_sort(graph, ancestor_ids):
        _raise_on_exception(await evaluator.evaluate(graph.cells[cid], glbls))

    _substitute_refs(cell_impl, glbls, kwargs)
    target_result = await evaluator.evaluate(
        graph.cells[cell_impl.cell_id], glbls
    )
    _raise_on_exception(target_result)
    return target_result.output, _returns(cell_impl, glbls)


def run_cell_sync(
    graph: DirectedGraph,
    cell_id: CellId_t,
    kwargs: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    """Run a synchronous cell and its ancestors.

    Substitutes kwargs as refs for the cell, omitting ancestors whose
    refs are substituted.

    Raises ``RuntimeError`` if the cell or any of its unsubstituted
    ancestors are coroutine functions.
    """
    from marimo._runtime.dataflow import topological_sort

    cell_impl = graph.cells[cell_id]
    if cell_impl.is_coroutine():
        raise RuntimeError(
            "A coroutine function can't be run synchronously. "
            "Use `run_async()` instead"
        )

    _validate_kwargs(cell_impl, kwargs)
    ancestor_ids = _get_ancestors(graph, cell_impl, kwargs)

    if any(graph.cells[cid].is_coroutine() for cid in ancestor_ids):
        raise RuntimeError(
            "Cell has an ancestor that is a "
            "coroutine (async) cell. Use `run_async()` instead"
        )

    evaluator = _new_evaluator()
    glbls: dict[str, Any] = {}
    for cid in topological_sort(graph, ancestor_ids):
        _raise_on_exception(evaluator.evaluate_sync(graph.cells[cid], glbls))

    _substitute_refs(cell_impl, glbls, kwargs)
    target_result = evaluator.evaluate_sync(
        graph.cells[cell_impl.cell_id], glbls
    )
    _raise_on_exception(target_result)
    return target_result.output, _returns(cell_impl, glbls)
