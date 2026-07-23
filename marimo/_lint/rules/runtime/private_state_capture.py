# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.variables import is_mangled_local, unmangle_local
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.breaking.graph import GraphRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._runtime.dataflow import DirectedGraph


class PrivateStateCaptureRule(GraphRule):
    """MR004: Top-level functions/classes capture private cell-local state.

    This rule warns when a top-level function or class closes over a private
    variable from the same cell. Private variables are intentionally excluded
    from the notebook dependency graph, so mutating them from a reusable
    definition can make behavior depend on execution order.

    ## Why is this bad?

    A function that closes over private cell state can appear pure while still
    hiding mutable state. When that function is called from different cells,
    the observed result may depend on which cells ran first.

    ## Example

    ```python
    _cache = {}


    def square(x):
        if x in _cache:
            return _cache[x] + 1
        _cache[x] = x * x
        return _cache[x]
    ```
    """

    code = "MR004"
    name = "private-state-capture"
    description = "Top-level definitions capture private cell-local state"
    severity = Severity.RUNTIME
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        for cell_id, cell in graph.cells.items():
            for (
                variable_name,
                variable_data_list,
            ) in cell.variable_data.items():
                for variable_data in variable_data_list:
                    if variable_data.kind not in {"function", "class"}:
                        continue

                    private_refs = sorted(
                        {
                            unmangle_local(ref, cell_id).name
                            for ref in variable_data.required_refs
                            if is_mangled_local(ref, cell_id)
                        }
                    )
                    if not private_refs:
                        continue

                    line, column = self._get_variable_line_info(
                        cell_id, variable_name, ctx
                    )
                    kind = (
                        "Function"
                        if variable_data.kind == "function"
                        else "Class"
                    )
                    refs = ", ".join(f"`{ref}`" for ref in private_refs)
                    await ctx.add_diagnostic(
                        Diagnostic(
                            message=(
                                f"{kind} '{variable_name}' captures private "
                                f"cell-local variable(s): {refs}"
                            ),
                            cell_id=[cell_id],
                            line=line,
                            column=column,
                            code=self.code,
                            name=self.name,
                            severity=self.severity,
                            fixable=self.fixable,
                            fix=(
                                "Use explicit cell outputs for shared state, or "
                                "use @mo.cache for memoized values."
                            ),
                        )
                    )
