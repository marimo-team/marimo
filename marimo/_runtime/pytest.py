# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

import marimo
from marimo._ast.pytest import MARIMO_TEST_STUB_NAME
from marimo._cli.print import bold, green
from marimo._runtime.capture import capture_stdout
from marimo._runtime.context import ContextNotInitializedError, get_context

MARIMO_TEST_BLOCK_REGEX = re.compile(rf"{MARIMO_TEST_STUB_NAME}_\d+[(?::)\.]+")


if TYPE_CHECKING:
    import _pytest  # type: ignore


@dataclass
class MarimoPytestResult:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    output: Optional[str] = None

    @property
    def total(self) -> int:
        return self.skipped + self.passed + self.failed + self.errors

    @property
    def summary(self) -> str:
        return (
            f"Total: {self.total}, Passed: {self.passed}, "
            f"Failed: {self.failed}, Errors: {self.errors}, "
            f"Skipped: {self.skipped}"
        )


def _maybe_name() -> str:
    try:
        ctx: Any = get_context()
        if ctx.filename is not None:
            filename = ctx.filename
    except ContextNotInitializedError:
        filename = "notebook.py"
    assert isinstance(filename, str)
    return filename


def _to_marimo_uri(uri: str) -> str:
    """Convert a file path URI to a marimo URI if it matches the cell pattern."""
    # Should be like
    # /tmp/marimo_1234567/__marimo__cell_1234_.py
    if "__marimo__cell_" not in uri:
        return uri
    cell_id = uri.split("_")[6]

    notebook = os.path.relpath(_maybe_name(), marimo.notebook_location())
    return f"marimo://{notebook}#cell_id={cell_id}"


def _sub_function(
    old_item: "_pytest.Item", parent: Any, fn: Callable[..., Any]
) -> "_pytest.Item":
    # Directly execute the cell, since this means it's a toplevel function with no deps.
    # Or a cell where which we already wrapped in skip.
    if isinstance(old_item.obj, marimo._ast.cell.Cell):
        return old_item

    import pytest  # type: ignore

    if hasattr(old_item, "callspec") and old_item.callspec:
        params: dict[str, Any] = old_item.callspec.params

        def make_test_func(
            func_JYWB: Callable[..., Any], param_dict: dict[str, Any]
        ) -> Callable[[], Any]:
            # note _JYWB is a suffix to easily detect in stack trace for
            # removal.
            # Also no functools.wraps(func) because we need the empty
            # call signature
            def test_wrapper() -> Any:
                return func_JYWB(**param_dict)

            # but copy attributes from the original function
            test_wrapper.__name__ = func_JYWB.__name__
            test_wrapper.__module__ = func_JYWB.__module__
            return test_wrapper

        fn = make_test_func(fn, params)
    pyfn = pytest.Function.from_parent(parent, name=old_item.name, callobj=fn)
    # Attributes that need to be carried over.
    for attr in ["keywords", "own_markers"]:
        if hasattr(old_item, attr):
            setattr(pyfn, attr, getattr(old_item, attr))
    return pyfn


class ReplaceStubPlugin:
    """Allows pytest to run in the runtime, by replacing the statically
    collected stubs with the runtime relevant implementations."""

    def __init__(
        self,
        defs: Optional[set[str]] = None,
        lcls: Optional[dict[str, Any]] = None,
    ) -> None:
        if lcls is None:
            lcls = globals()
        if defs is None:
            defs = set(lcls.keys())

        self.lcls = lcls
        self.defs = defs
        self._result = MarimoPytestResult()

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        """Provided pytest has statically collected all the relevant tests:
        - Filter based on the expected defs of the cell context.
        - Sub in the function references in scope opposed to the pytest
          determined stubs.
        """
        # Not official marimo dependencies
        # So don't import at the top level.
        import _pytest  # type: ignore

        to_collect = []
        # Filter tests, and create new "Functions" with the relevant references
        # where needed.
        for i, item in enumerate(items):
            head: Any = item
            path: list[str] = []

            while isinstance(head.parent.parent, _pytest.python.Class):
                path.append(head.name)
                head = head.parent

            # For test name, helps keep names relative to the root.
            parent: Any = item.parent
            if not path:
                parent = parent.parent

            name: str = getattr(head, "originalname", head.name)
            if name in self.defs:
                obj: Any = self.lcls[name]
                for attr in reversed(path):
                    if isinstance(obj, type):
                        obj = obj()
                    obj = getattr(obj, attr)
                to_collect.append(_sub_function(items[i], parent, obj))
        items[:] = to_collect

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
        self._result = MarimoPytestResult(
            passed=passed, failed=failed, errors=errors, skipped=skipped
        )

        tr.write_line(self._result.summary)

    def pytest_runtest_logreport(
        self, report: "_pytest.reports.TestReport"
    ) -> None:
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
        if report.longrepr:
            if isinstance(report.longrepr, tuple):
                _, lineno, msg = report.longrepr
                report.longrepr = (report.nodeid, lineno, f"({msg})")
            elif not isinstance(report.longrepr, str):
                longrepr = str(report.longrepr)
                if "func_JYWB" in longrepr:
                    # Strip the first call of traceback
                    report.longrepr.reprtraceback.reprentries = (
                        report.longrepr.reprtraceback.reprentries[1:]
                    )
                for entry in report.longrepr.reprtraceback.reprentries:
                    entry.reprfileloc.path = _to_marimo_uri(
                        entry.reprfileloc.path
                    )


def run_pytest(
    defs: set[str] | None = None,
    lcls: dict[str, Any] | None = None,
    notebook_path: Path | str | None = None,
) -> MarimoPytestResult:
    import pytest  # type: ignore

    if not notebook_path:
        # Translate name to python module
        notebook_path = os.path.relpath(
            _maybe_name(), marimo.notebook_location()
        )
    notebook_path = str(notebook_path)
    # So path/to/notebook.py -> path.to.notebook
    # but windows compat
    notebook = (
        notebook_path.replace(os.sep, ".").strip(".py").strip(".md")
    ).strip(".")

    if notebook in sys.modules:
        del sys.modules[notebook]

    # qq and disable warnings suppress a fair bit of filler noise.
    # color=yes seems to work nicely, but code-highlight is a bit much.
    plugin = ReplaceStubPlugin(defs, lcls)
    with capture_stdout() as stdout:
        pytest.main(
            [
                "-qq",
                "--disable-warnings",
                "--color=yes",
                "--code-highlight=no",
                notebook_path,
            ],
            plugins=[plugin],
        )

    plugin._result.output = stdout.getvalue()
    return plugin._result
