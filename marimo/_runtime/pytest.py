# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import os
import re
import sys
import types
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from marimo._ast.pytest import MARIMO_TEST_STUB_NAME
from marimo._ast.variables import demangle_locals_in_text
from marimo._cli.print import bold, green
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.capture import capture_stdout
from marimo._runtime.context import safe_get_context
from marimo._runtime.runtime import notebook_location

MARIMO_TEST_BLOCK_REGEX = re.compile(rf"{MARIMO_TEST_STUB_NAME}_\d+[(?::)\.]+")


if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from _pytest.nodes import Collector, Item, Node

    class _LiveModule(pytest.Module):
        def _set_globals(self, _marimo_globals: dict[str, Any]) -> None: ...


@dataclass
class MarimoPytestResult:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    xfailed: int = 0
    xpassed: int = 0
    output: str | None = None

    @property
    def total(self) -> int:
        return (
            self.passed
            + self.failed
            + self.errors
            + self.skipped
            + self.xfailed
            + self.xpassed
        )

    @property
    def summary(self) -> str:
        parts = [
            f"Total: {self.total}",
            f"Passed: {self.passed}",
            f"Failed: {self.failed}",
            f"Errors: {self.errors}",
            f"Skipped: {self.skipped}",
        ]
        if self.xfailed:
            parts.append(f"XFailed: {self.xfailed}")
        if self.xpassed:
            parts.append(f"XPassed: {self.xpassed}")
        return ", ".join(parts)


def _get_name(default: str = "notebook.py") -> str:
    filename = default
    ctx = safe_get_context()
    if ctx and ctx.filename is not None:
        filename = ctx.filename
    return filename


def _to_marimo_uri(uri: str) -> str:
    """Convert a file path URI to a marimo URI if it matches the cell pattern."""
    # Should be like
    # /tmp/marimo_1234567/__marimo__cell_1234_.py
    if "__marimo__cell_" not in uri:
        return uri
    cell_id = uri.split("_")[6]

    notebook = os.path.relpath(_get_name(), notebook_location())
    return f"marimo://{notebook}#cell_id={cell_id}"


def _rewrite_longrepr(longrepr: Any) -> None:
    """Rewrite a TerminalRepr in place for user-friendly test output.

    Strips the parameter-workaround frame at the top of the traceback,
    rewrites each entry's file location into a `marimo://` URI, and
    demangles `_cell_<id>_<name>` -> `<_name>` in source/exception lines
    and the short-summary `reprcrash.message`.
    """
    if "func_JYWB" in str(longrepr):
        longrepr.reprtraceback.reprentries = (
            longrepr.reprtraceback.reprentries[1:]
        )
    for entry in longrepr.reprtraceback.reprentries:
        if entry.reprfileloc is not None:
            entry.reprfileloc.path = _to_marimo_uri(entry.reprfileloc.path)
        if getattr(entry, "lines", None):
            entry.lines = [
                demangle_locals_in_text(line) for line in entry.lines
            ]
    reprcrash = getattr(longrepr, "reprcrash", None)
    if reprcrash is not None and reprcrash.message:
        reprcrash.message = demangle_locals_in_text(reprcrash.message)


def _is_fixture(obj: Any) -> bool:
    """Whether `obj` is a pytest fixture.

    pytest <9 tags the function with `_pytestfixturefunction`; pytest >=9 wraps
    it in a `FixtureFunctionDefinition`. Duck-typed on the class name to avoid a
    private import that doesn't exist across both.
    """
    return hasattr(obj, "_pytestfixturefunction") or (
        type(obj).__name__ == "FixtureFunctionDefinition"
    )


def _global_scope_defs() -> set[str]:
    """Names visible to every cell: the setup cell and top-level
    (`@app.function` / `@app.class_definition`) definitions.

    Used to determine notebook-global fixtures for live collection.
    Returns an empty set when no kernel context is available.
    """
    from marimo._ast.names import SETUP_CELL_NAME

    ctx = safe_get_context()
    if ctx is None:
        return set()
    graph = ctx.graph
    hint = graph.cells_serving_serialization_hint
    out: set[str] = set()
    for cid, cell in graph.cells.items():
        if str(cid) == SETUP_CELL_NAME or cid in hint:
            out |= cell.defs
    return out


@functools.cache
def _live_module_cls() -> type[_LiveModule]:
    """`pytest.Module` that collects from the kernel's live globals.

    The kernel has already executed the notebook's cells, so the live test
    objects — carrying the user's current (possibly unsaved) definitions and
    `@parametrize` markers — are sitting in the run namespace.

    Defined lazily because pytest is an optional dependency.
    """
    import pytest

    class _LiveModuleImpl(pytest.Module):
        _marimo_globals: dict[str, Any]

        def _set_globals(self, _marimo_globals: dict[str, Any]) -> None:
            self._marimo_globals = _marimo_globals

        def _getobj(self) -> types.ModuleType:
            module = types.ModuleType(self.path.stem)
            module.__file__ = str(self.path)
            # Copy in: pytest mutates the module dict during collection, so we
            # must not alias (and pollute) the live kernel namespace.
            module.__dict__.update(self._marimo_globals)
            return module

    return cast("type[_LiveModule]", _LiveModuleImpl)


class ReplaceStubPlugin:
    """Allows pytest to run in the runtime, by replacing the statically
    collected stubs with the runtime relevant implementations."""

    def __init__(
        self,
        defs: set[str] | None = None,
        lcls: dict[str, Any] | None = None,
        global_defs: set[str] | None = None,
    ) -> None:
        if lcls is None:
            lcls = globals()
        if defs is None:
            defs = set(lcls.keys())

        self.lcls = lcls
        self.defs = defs
        # Notebook-global names (setup + top-level defs). Together with `defs`
        # they bound which fixtures stay visible during live collection; any
        # fixture outside this scope belongs to a sibling cell and is hidden to
        # preserve cell isolation.
        self.global_defs = global_defs or set()
        self._result = MarimoPytestResult()

    def _live_module_globals(self) -> dict[str, Any]:
        """The kernel globals, minus fixtures owned by sibling cells.

        Non-fixture names are kept wholesale so cross-cell variable refs and
        decorator values resolve. Fixtures are kept only when in scope (this
        run's `defs` or a notebook-global def); a sibling cell's fixture is
        dropped so a test referencing it errors with "fixture not found",
        preserving cell isolation.
        """
        scope = self.defs | self.global_defs
        return {
            name: value
            for name, value in self.lcls.items()
            if name in scope or not _is_fixture(value)
        }

    def pytest_pycollect_makemodule(
        self, module_path: Path, parent: Collector
    ) -> _LiveModule:
        """Collect from the kernel's live globals rather than disk."""
        module = _live_module_cls().from_parent(parent, path=module_path)
        module._set_globals(self._live_module_globals())
        return module

    def _live_owner(self, item: Item) -> str | None:
        """Name of the module-level object (function/class) owning `item`."""
        import pytest

        node: Node = item
        while node.parent is not None and not isinstance(
            node.parent, pytest.Module
        ):
            node = node.parent
        if node.parent is None:
            return None
        name = getattr(node, "originalname", node.name)
        return name if isinstance(name, str) else None

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Filter to just the items owned by this cell's defs.

        Items were collected from the live kernel globals, so they are
        already the runtime implementations with current markers, and the
        in-scope fixtures are present in the synthetic module (see
        `_live_module_globals`).
        """
        items[:] = [
            item for item in items if self._live_owner(item) in self.defs
        ]

    def pytest_terminal_summary(self, terminalreporter: Any) -> None:
        """Provide a clean summary of test results. Gives something like:
        =========== Overview ===========
        Passed Tests:
        ✓ testing.py::test_sanity
        ✓ testing.py::test_parameterized_collected[3-4]
        ✓ testing.py::test_parameterized_collected[4-5]
        ✓ testing.py::TestWhatever::test_class_def

        Summary:
        Total: 9, Passed: 4, Failed: 4, Errors: 0, Skipped: 1
        """

        tr: Any = terminalreporter
        tr.write_sep("=", "Overview")
        stats: dict[str, Any] = tr.stats

        # Failures and non passes are shown in summary.
        # Display successes here manually since -v is a little too noisy.
        if "passed" in stats:
            tr.write_line("Passed Tests:")
            for rep in stats["passed"]:
                tr.write_line(f"{bold(green('✓'))} {rep.nodeid}")

        tr.write_line("\nSummary:")
        passed: int = len(stats.get("passed", []))
        failed: int = len(stats.get("failed", []))
        skipped: int = len(stats.get("skipped", []))
        errors: int = len(stats.get("error", []))
        xfailed: int = len(stats.get("xfailed", []))
        xpassed: int = len(stats.get("xpassed", []))
        self._result = MarimoPytestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            xfailed=xfailed,
            xpassed=xpassed,
        )

        tr.write_line(self._result.summary)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """In place updates the report for some better formatting.
        In particular:
           - removes stub class reference for scoped tests
           - removes extra frame from parameter workaround
           - fixes test name/ paths to be more consistent with expectation
        """
        report.nodeid = MARIMO_TEST_BLOCK_REGEX.sub("", report.nodeid)
        if report.location is not None:
            fspath, lineno, domain = report.location
            report.location = (
                fspath,
                lineno,
                MARIMO_TEST_BLOCK_REGEX.sub("", domain),
            )
        # Signature from pytest for longrepr is:
        # None | ExceptionInfo[BaseException] | tuple[str, int, str] | str | TerminalRepr
        if not report.longrepr or isinstance(report.longrepr, str):
            return

        if isinstance(report.longrepr, tuple):
            _, lineno, msg = report.longrepr
            report.longrepr = (report.nodeid, lineno, f"({msg})")
        # Not all TerminalRepr seem to have a reprtraceback.
        elif hasattr(report.longrepr, "reprtraceback"):
            _rewrite_longrepr(report.longrepr)


def run_pytest(
    defs: set[str] | None = None,
    lcls: dict[str, Any] | None = None,
    notebook_path: Path | str | None = None,
    global_defs: set[str] | None = None,
) -> MarimoPytestResult:
    # Collection reads the kernel's live globals (see
    # ReplaceStubPlugin.pytest_pycollect_makemodule).
    DependencyManager.pytest.require(
        "pytest is required for reactive "
        "testing. Please report to github if you would like a different testing "
        "suite supported."
    )

    import pytest

    if not notebook_path:
        # Translate name to python module
        notebook_path = _get_name()
    notebook_path = str(notebook_path)

    if global_defs is None:
        # In the kernel this resolves setup + top-level defs from the live
        # graph; with no context (e.g. direct `app.run()`) it is empty and the
        # caller may pass an explicit set.
        global_defs = _global_scope_defs()

    # Hold on to modules since we want to refresh them in order to enable
    # repeated calls.
    module_snapshot = dict(sys.modules)
    # Paths may be altered by pytest. To prevent accumulation- we refresh the
    # path to the original state.
    # NB. refer to pytester the most native solution (not used here, since it
    # seems reasonable to just hook in this way).
    path_snapshot = sys.path.copy()

    # qq and disable warnings suppress a fair bit of filler noise.
    # color=yes seems to work nicely, but code-highlight is a bit much.
    # Ideally, --import-mode=importlib would be a great flag- however the
    # method is too brittle to handle absolute paths. As such, we default to
    # the normal behavior (in which pytest alters the system path).
    plugin = ReplaceStubPlugin(defs, lcls, global_defs=global_defs)
    try:
        # pytest in wasm doesn't seem to set environment variables correctly.
        # This work around is to prevent collision with non-wasm testing.
        os.environ["MARIMO_PYTEST_WASM"] = "1"
        with capture_stdout() as stdout:
            pytest.main(
                [
                    "-qq",
                    "--disable-warnings",
                    "--color=yes",
                    "--code-highlight=no",
                    "-p",
                    "no:codecov",  # Disable codecov plugin to avoid duplicate reports
                    "-p",
                    "no:sugar",  # Disable sugar plugin to avoid duplicate reports
                    "-p",
                    "no:cacheprovider",  # Skip .pytest_cache I/O
                    notebook_path,
                ],
                plugins=[plugin],
            )
    finally:
        del os.environ["MARIMO_PYTEST_WASM"]
        # Note, in pytester, there are also exceptions for zope and readline.
        # However, those deps should already be in module_snapshot, since
        # dependencies are required before the given cell runs.
        sys.modules.clear()
        sys.modules.update(module_snapshot)
        sys.path[:] = path_snapshot

    plugin._result.output = stdout.getvalue()
    return plugin._result
