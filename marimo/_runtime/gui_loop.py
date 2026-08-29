# Copyright 2026 Marimo. All rights reserved.
"""GUI toolkit event loop integration for the kernel.

The kernel's control loop is an asyncio loop; GUI toolkits like Qt only
repaint and react to input while *their* event loop runs. Instead of asking
every GUI library to hand-roll a `processEvents()` polling task, the kernel's
asyncio loop itself can be one that also services the toolkit — for Qt, via
`qasync`, which implements an asyncio event loop on top of a running
QApplication. See https://github.com/marimo-team/marimo/issues/1986.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._config.config import GuiEventLoopType
from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from collections.abc import Callable

LOGGER = _loggers.marimo_logger()

# Qt bindings qasync supports, in its own probe order. qasync's probe does a
# bare `import PyQt5` etc., which false-positives on partial installs (a stray
# PyQt5-Qt5 wheel leaves an importable PyQt5 namespace package with no
# QtCore), so we import the binding — verified via QtCore — before importing
# qasync, which then keys its detection on sys.modules.
QT_BINDINGS = ("PyQt5", "PyQt6", "PySide2", "PySide6")

# Values of the conventional QT_API environment variable (as used by qtpy and
# qasync's own examples), mapped to importable module names.
_QT_API_TO_BINDING = {name.lower(): name for name in QT_BINDINGS}


def _import_qt_binding() -> str:
    """Import one Qt binding and return its module name.

    Preference order: a binding that is already imported (user code or a
    launcher chose it), then the `QT_API` environment variable, then the
    first binding that imports cleanly.
    """
    candidates: list[str] = []
    for name in QT_BINDINGS:
        if name in sys.modules:
            candidates.append(name)
    qt_api = _QT_API_TO_BINDING.get(os.environ.get("QT_API", "").lower())
    if qt_api is not None and qt_api not in candidates:
        candidates.append(qt_api)
    candidates.extend(name for name in QT_BINDINGS if name not in candidates)

    for name in candidates:
        already_imported = name in sys.modules
        try:
            importlib.import_module(f"{name}.QtCore")
        except ImportError:
            if not already_imported:
                # a failed `import PyQt5.QtCore` leaves the (namespace)
                # parent package in sys.modules, which qasync's own
                # sys.modules-based detection would then pick and crash on
                sys.modules.pop(name, None)
            continue
        return name
    raise ModuleNotFoundError(
        "The 'qt' GUI event loop requires a Qt binding; install one with "
        "e.g. `pip install PySide6`."
    )


def make_gui_loop_factory(
    kind: GuiEventLoopType,
) -> Callable[[], asyncio.AbstractEventLoop]:
    """Return an asyncio loop factory that also runs `kind`'s event loop.

    Raises if `kind` is unsupported or its dependencies are missing; callers
    should treat that as non-fatal and fall back to a plain asyncio loop.
    """
    if kind != "qt":
        raise ValueError(
            f"Unsupported gui_event_loop {kind!r}; supported values: 'qt'"
        )
    binding = _import_qt_binding()
    DependencyManager.qasync.require(
        why=f"to drive the {binding} event loop (runtime.gui_event_loop)"
    )
    import qasync  # type: ignore[import-not-found,import-untyped,unused-ignore]

    def factory() -> asyncio.AbstractEventLoop:
        app = qasync.QApplication.instance()
        if app is None:
            app = qasync.QApplication([sys.executable])
        # The Qt loop *is* the kernel's loop: closing the last window (which
        # quits the QApplication by default) must not stop the kernel.
        app.setQuitOnLastWindowClosed(False)
        loop = qasync.QEventLoop(app, set_running_loop=False)
        LOGGER.debug("Created qasync event loop over %s", binding)
        return cast(asyncio.AbstractEventLoop, loop)

    return factory
