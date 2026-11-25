# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._runtime.runner.hooks import (
    NotebookCellHooks,
    Priority,
    create_default_hooks,
)


@pytest.fixture
def hooks() -> NotebookCellHooks:
    return NotebookCellHooks()


class TestNotebookCellHooks:
    def test_add_and_retrieve(self, hooks: NotebookCellHooks) -> None:
        hook = lambda _: None  # noqa: E731
        hooks.add_preparation(hook)
        assert hook in hooks.preparation_hooks

    def test_priority_ordering(self, hooks: NotebookCellHooks) -> None:
        order: list[str] = []

        hooks.add_post_execution(
            lambda _c, _r, _res: order.append("late"), Priority.LATE
        )
        hooks.add_post_execution(
            lambda _c, _r, _res: order.append("early"), Priority.EARLY
        )
        hooks.add_post_execution(
            lambda _c, _r, _res: order.append("final"), Priority.FINAL
        )
        hooks.add_post_execution(lambda _c, _r, _res: order.append("normal"))

        for hook in hooks.post_execution_hooks:
            hook(None, None, None)  # type: ignore

        assert order == ["early", "normal", "late", "final"]

    def test_copy_is_independent(self, hooks: NotebookCellHooks) -> None:
        hook1 = lambda _: None  # noqa: E731
        hooks.add_preparation(hook1)

        hooks_copy = hooks.copy()
        hook2 = lambda _: None  # noqa: E731
        hooks_copy.add_preparation(hook2)

        assert len(hooks.preparation_hooks) == 1
        assert len(hooks_copy.preparation_hooks) == 2


class TestCreateDefaultHooks:
    def test_creates_all_hook_types(self) -> None:
        hooks = create_default_hooks()
        assert len(hooks.preparation_hooks) > 0
        assert len(hooks.pre_execution_hooks) > 0
        assert len(hooks.post_execution_hooks) > 0
        assert len(hooks.finalization_hooks) > 0
        assert len(hooks.on_finish_hooks) > 0

    def test_set_status_idle_is_last_finalization_hook(self) -> None:
        """Verify _set_status_idle runs after flushing console output.

        This is important because status should only be set to idle after all
        other post-execution work (like broadcasting outputs) is complete.
        """
        from marimo._runtime.runner.hooks_post_execution import (
            _flush_console,
            _set_status_idle,
        )

        hooks = create_default_hooks()
        assert hooks.finalization_hooks == [_flush_console, _set_status_idle]
        assert _flush_console not in hooks.post_execution_hooks
        assert _set_status_idle not in hooks.post_execution_hooks


class TestSetRunResultStatus:
    """`MarimoInterrupt` in `run_result.exception` must map to the
    `interrupted` status so the UI distinguishes user-stop from error.
    """

    def _hook(self, exception, cancelled_cells=None):  # type: ignore[no-untyped-def]
        from unittest.mock import MagicMock

        from marimo._runtime.runner.hooks_post_execution import (
            _set_run_result_status,
        )
        from marimo._runtime.runner.result import RunResult

        cell = MagicMock()
        cell.cell_id = "c0"
        ctx = MagicMock()
        ctx.cancelled_cells = cancelled_cells or set()
        run_result = RunResult(output=None, exception=exception)
        _set_run_result_status(cell, ctx, run_result)
        return cell.set_run_result_status.call_args

    def test_marimo_interrupt_sets_interrupted(self) -> None:
        from marimo._runtime.control_flow import MarimoInterrupt

        call = self._hook(MarimoInterrupt())

        assert call is not None
        assert call.args[0] == "interrupted"

    def test_marimo_interrupt_takes_precedence_over_cancelled(self) -> None:
        """Interrupt wins over cancellation: a cell that interrupted
        itself also lands in `cancelled_cells` via its descendants pass."""
        from marimo._runtime.control_flow import MarimoInterrupt

        call = self._hook(MarimoInterrupt(), cancelled_cells={"c0"})

        assert call is not None
        assert call.args[0] == "interrupted"

    def test_cancelled_when_not_interrupt(self) -> None:
        call = self._hook(ValueError("boom"), cancelled_cells={"c0"})

        assert call is not None
        assert call.args[0] == "cancelled"

    def test_exception_when_not_interrupt_or_cancelled(self) -> None:
        call = self._hook(ValueError("boom"))

        assert call is not None
        assert call.args[0] == "exception"

    def test_no_exception_is_success(self) -> None:
        call = self._hook(None)

        assert call is not None
        assert call.args[0] == "success"


@pytest.mark.parametrize("imported", [False, True])
def test_duckdb_hook_does_not_discover_packages(imported: bool) -> None:
    from unittest.mock import Mock, patch

    from marimo._ast.compiler import compile_cell
    from marimo._dependencies.dependencies import DependencyManager
    from marimo._runtime.runner import hooks_post_execution as hooks

    cell = compile_cell(
        'db.execute("CREATE TABLE t (x INTEGER)")', cell_id="cell"
    )
    with (
        patch.object(
            DependencyManager.duckdb, "imported", return_value=imported
        ),
        patch.object(DependencyManager.duckdb, "has") as discover,
        patch.object(hooks, "has_updates_to_datasource", return_value=True),
        patch.object(hooks, "DuckDBEngine") as engine,
        patch.object(hooks, "engine_to_data_source_connection"),
        patch.object(hooks, "broadcast_notification") as broadcast,
    ):
        hooks._broadcast_duckdb_datasource(
            cell, Mock(should_broadcast_data=True), Mock()
        )
        discover.assert_not_called()
        assert engine.call_count == int(imported)
        assert broadcast.call_count == int(imported)
        assert ("sqls" in cell.__dict__) == imported


def test_state_hook_checks_membership_without_enumerating_names() -> None:
    from unittest.mock import Mock, patch

    from marimo._ast.compiler import compile_cell
    from marimo._runtime.runner.hook_context import (
        CancelledCells,
        PostExecutionHookContext,
    )
    from marimo._runtime.runner.hooks_post_execution import (
        _store_state_reference,
    )
    from marimo._runtime.state import State, StateRegistry

    class MembershipOnlyDict(dict[str, set[str]]):
        def __iter__(self):
            raise AssertionError("Do not enumerate notebook definitions")

        def keys(self):
            raise AssertionError("Do not enumerate notebook definitions")

    registry = StateRegistry()
    states = {
        name: State(0, _registry=registry, _name=name)
        for name in ["public", "temporary", "deleted"]
    }
    ctx = PostExecutionHookContext(
        graph=Mock(definitions=MembershipOnlyDict(public={"cell"})),
        glbls={},
        execution_context=None,
        exceptions={},
        cancelled_cells=CancelledCells(),
        all_temporaries=frozenset({"temporary"}),
    )
    with patch(
        "marimo._runtime.runner.hooks_post_execution.get_context",
        return_value=Mock(state_registry=registry),
    ):
        _store_state_reference(compile_cell("", cell_id="cell"), ctx, Mock())
    assert {name: registry.lookup(name) for name in states} == {
        "public": states["public"],
        "temporary": states["temporary"],
        "deleted": None,
    }
