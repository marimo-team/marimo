from __future__ import annotations

import asyncio
import importlib.machinery
import sys
import types
from typing import TYPE_CHECKING

import pytest

from marimo._config.config import merge_default_config
from marimo._runtime import gui_loop
from marimo._runtime.runtime import _asyncio_run, _maybe_gui_loop_factory

if TYPE_CHECKING:
    from pathlib import Path

FAKE_BINDING = "PySide6"


def _install_fake_binding(
    monkeypatch: pytest.MonkeyPatch, name: str = FAKE_BINDING
) -> types.ModuleType:
    binding = types.ModuleType(name)
    qtcore = types.ModuleType(f"{name}.QtCore")
    monkeypatch.setitem(sys.modules, name, binding)
    monkeypatch.setitem(sys.modules, f"{name}.QtCore", qtcore)
    return binding


def _install_fake_qasync(
    monkeypatch: pytest.MonkeyPatch,
) -> types.ModuleType:
    qasync = types.ModuleType("qasync")
    # a real ModuleSpec so importlib.util.find_spec (DependencyManager.has)
    # sees the injected module as installed
    qasync.__spec__ = importlib.machinery.ModuleSpec("qasync", loader=None)

    class FakeQApplication:
        _instance: FakeQApplication | None = None

        def __init__(self, argv: list[str]) -> None:
            self.argv = argv
            self.quit_on_last_window_closed = True
            FakeQApplication._instance = self

        @classmethod
        def instance(cls) -> FakeQApplication | None:
            return cls._instance

        def setQuitOnLastWindowClosed(self, value: bool) -> None:
            self.quit_on_last_window_closed = value

    class FakeQEventLoop(asyncio.SelectorEventLoop):
        def __init__(
            self, app: FakeQApplication, set_running_loop: bool = False
        ) -> None:
            super().__init__()
            # the factory must not use qasync's deprecated auto-set behavior
            assert set_running_loop is False
            self.app = app

    qasync.QApplication = FakeQApplication
    qasync.QEventLoop = FakeQEventLoop
    monkeypatch.setitem(sys.modules, "qasync", qasync)
    return qasync


def test_unsupported_kind_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported gui_event_loop"):
        gui_loop.make_gui_loop_factory("tk")  # type: ignore[arg-type]


def test_no_binding_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", ())
    with pytest.raises(ModuleNotFoundError, match="requires a Qt binding"):
        gui_loop.make_gui_loop_factory("qt")


def test_partial_binding_install_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An importable binding package without QtCore (e.g. the namespace left
    # behind by a PyQt5-Qt5 wheel) must not satisfy the probe.
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", ("PartialQt",))
    monkeypatch.setitem(
        sys.modules, "PartialQt", types.ModuleType("PartialQt")
    )
    with pytest.raises(ModuleNotFoundError, match="requires a Qt binding"):
        gui_loop.make_gui_loop_factory("qt")


def test_failed_probe_does_not_pollute_sys_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Probing `import PartialQt.QtCore` imports the parent package as a side
    # effect; if a partial install (a bare namespace directory) stays in
    # sys.modules, qasync's own sys.modules-based detection picks it and
    # crashes. The probe must clean up what it imported.
    (tmp_path / "PartialQt").mkdir()  # importable namespace pkg, no QtCore
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", ("PartialQt", FAKE_BINDING))
    _install_fake_binding(monkeypatch)
    _install_fake_qasync(monkeypatch)

    gui_loop.make_gui_loop_factory("qt")
    assert "PartialQt" not in sys.modules


def test_factory_builds_qasync_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", (FAKE_BINDING,))
    _install_fake_binding(monkeypatch)
    qasync = _install_fake_qasync(monkeypatch)

    factory = gui_loop.make_gui_loop_factory("qt")
    loop = factory()
    try:
        assert isinstance(loop, qasync.QEventLoop)
        assert loop.app is qasync.QApplication.instance()
        # closing the last window must not stop the kernel's loop
        assert loop.app.quit_on_last_window_closed is False
        # the loop is a real asyncio loop: it can run a coroutine
        assert loop.run_until_complete(asyncio.sleep(0, result=42)) == 42
    finally:
        loop.close()

    # a second loop reuses the existing QApplication
    app = qasync.QApplication.instance()
    loop = factory()
    try:
        assert loop.app is app
    finally:
        loop.close()


def _config(gui_event_loop: str | None):
    partial = (
        {"runtime": {"gui_event_loop": gui_event_loop}}
        if gui_event_loop is not None
        else {}
    )
    return merge_default_config(partial)


def test_resolve_unset_returns_fallback() -> None:
    fallback = object()
    assert (
        _maybe_gui_loop_factory(
            _config(None), is_subprocess=True, fallback=fallback
        )
        is fallback
    )


def test_resolve_ignored_in_run_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", (FAKE_BINDING,))
    _install_fake_binding(monkeypatch)
    _install_fake_qasync(monkeypatch)
    fallback = object()
    assert (
        _maybe_gui_loop_factory(
            _config("qt"), is_subprocess=False, fallback=fallback
        )
        is fallback
    )


def test_resolve_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    # missing toolkit must not prevent the kernel from starting
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", ())
    fallback = object()
    assert (
        _maybe_gui_loop_factory(
            _config("qt"), is_subprocess=True, fallback=fallback
        )
        is fallback
    )


def test_resolve_returns_gui_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", (FAKE_BINDING,))
    _install_fake_binding(monkeypatch)
    qasync = _install_fake_qasync(monkeypatch)
    factory = _maybe_gui_loop_factory(
        _config("qt"), is_subprocess=True, fallback=None
    )
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, qasync.QEventLoop)
    finally:
        loop.close()


def test_asyncio_run_with_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    # the kernel entrypoint must run its coroutine on the factory's loop on
    # every supported Python version
    monkeypatch.setattr(gui_loop, "QT_BINDINGS", (FAKE_BINDING,))
    _install_fake_binding(monkeypatch)
    qasync = _install_fake_qasync(monkeypatch)
    factory = gui_loop.make_gui_loop_factory("qt")
    ran_on: list[asyncio.AbstractEventLoop] = []

    async def main() -> None:
        ran_on.append(asyncio.get_running_loop())

    _asyncio_run(main(), factory)
    assert len(ran_on) == 1
    assert isinstance(ran_on[0], qasync.QEventLoop)
