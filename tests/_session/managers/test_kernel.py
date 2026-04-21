# Copyright 2026 Marimo. All rights reserved.
"""Tests for KernelManagerImpl's host __main__ save/restore methods.

These methods are the application-layer glue between ``KernelManagerImpl``
and the refcounted save/restore primitives in ``marimo._runtime.patches``.
They own the per-instance flag and lock that make the wrappers idempotent
against double ``close_kernel`` calls and concurrent callers.
"""

from __future__ import annotations

import sys
import threading

from marimo._runtime import patches
from marimo._session.managers.kernel import KernelManagerImpl


def _make_bare_kernel_manager() -> KernelManagerImpl:
    """Return an uninitialized KernelManagerImpl with only the state that
    ``_save_host_main_module`` and ``_restore_host_main_module`` touch.

    Bypasses ``__init__`` so the test does not need to construct a real
    queue manager, session config, etc.
    """
    km = object.__new__(KernelManagerImpl)
    km._main_save_lock = threading.Lock()
    km._main_save_outstanding = False
    return km


def _expected_refcount() -> int:
    """Current value of the module-level save refcount for assertions."""
    return patches._main_save_count


class TestSaveHostMainModule:
    def test_save_sets_outstanding_flag(self) -> None:
        km = _make_bare_kernel_manager()
        assert km._main_save_outstanding is False
        km._save_host_main_module()
        try:
            assert km._main_save_outstanding is True
        finally:
            km._restore_host_main_module()

    def test_save_is_idempotent(self) -> None:
        """A second save call without a restore must not double-increment."""
        km = _make_bare_kernel_manager()
        before = _expected_refcount()
        km._save_host_main_module()
        try:
            after_first = _expected_refcount()
            km._save_host_main_module()
            after_second = _expected_refcount()
            assert after_first - before == 1
            assert after_second == after_first
        finally:
            km._restore_host_main_module()
        assert _expected_refcount() == before

    def test_save_without_restore_leaves_refcount_held(self) -> None:
        """Documents the leak contract: an unbalanced save holds the
        process refcount and the per-instance flag until a paired restore
        releases them. A caller that never calls ``close_kernel`` (e.g.
        process exits abnormally) leaves the host ``__main__`` polluted;
        this is the expected degraded behavior.
        """
        km = _make_bare_kernel_manager()
        before = _expected_refcount()
        km._save_host_main_module()
        try:
            assert km._main_save_outstanding is True
            assert _expected_refcount() == before + 1
        finally:
            # Release so the leak does not cascade into other tests.
            km._restore_host_main_module()
        assert km._main_save_outstanding is False
        assert _expected_refcount() == before


class TestRestoreHostMainModule:
    def test_restore_without_save_is_noop(self) -> None:
        km = _make_bare_kernel_manager()
        before = _expected_refcount()
        km._restore_host_main_module()
        assert km._main_save_outstanding is False
        assert _expected_refcount() == before

    def test_restore_is_idempotent(self) -> None:
        """Blocker repro: double close_kernel must not over-release.

        Two ``KernelManagerImpl`` instances share the process refcount;
        if one calls ``_restore_host_main_module`` twice, the second call
        must not decrement the refcount and prematurely restore ``__main__``
        while the other instance is still holding a save.
        """
        other = _make_bare_kernel_manager()
        me = _make_bare_kernel_manager()
        # ``other`` mimics a second session still holding a save.
        other._save_host_main_module()
        try:
            me._save_host_main_module()
            with_both = _expected_refcount()

            me._restore_host_main_module()
            after_first_release = _expected_refcount()
            assert after_first_release == with_both - 1
            assert me._main_save_outstanding is False

            # Second call from the same instance: no effect on refcount.
            me._restore_host_main_module()
            assert _expected_refcount() == after_first_release
            assert me._main_save_outstanding is False
        finally:
            other._restore_host_main_module()

    def test_concurrent_restores_do_not_double_release(self) -> None:
        """Many threads racing on restore release the refcount exactly once."""
        other = _make_bare_kernel_manager()
        me = _make_bare_kernel_manager()
        other._save_host_main_module()
        try:
            me._save_host_main_module()
            before = _expected_refcount()

            barrier = threading.Barrier(8)

            def worker() -> None:
                barrier.wait()
                me._restore_host_main_module()

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert me._main_save_outstanding is False
            assert _expected_refcount() == before - 1
        finally:
            other._restore_host_main_module()


class TestSaveRestoreIntegration:
    def test_cycle_returns_main_to_host_original(self) -> None:
        """Full save-patch-restore via the wrapper methods leaves main intact."""
        km = _make_bare_kernel_manager()
        original = sys.modules["__main__"]

        km._save_host_main_module()
        try:
            patches.patch_main_module(
                file=None, input_override=None, print_override=None
            )
            assert sys.modules["__main__"] is not original
        finally:
            km._restore_host_main_module()

        assert sys.modules["__main__"] is original
