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
        assert len(hooks.on_finish_hooks) > 0

    def test_set_status_idle_is_last_post_execution_hook(self) -> None:
        """Verify _set_status_idle is the last hook in POST_EXECUTION_HOOKS.

        This is important because status should only be set to idle after all
        other post-execution work (like broadcasting outputs) is complete.
        """
        from marimo._runtime.runner.hooks_post_execution import (
            POST_EXECUTION_HOOKS,
            _set_status_idle,
        )

        assert POST_EXECUTION_HOOKS[-1] is _set_status_idle
