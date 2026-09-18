from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.mocks import snapshotter

if TYPE_CHECKING:
    from marimo._runtime.pytest import run_pytest as _run_pytest_type
    from tests._runtime.script_data.contains_tests import app as _app_type

snapshot = snapshotter(__file__)

# Format: (passed, skipped, failed, errors)
_DEF_COUNT = {
    # fixtures, not tests
    "function_fixture": (0, 0, 0, 0),
    "scoped_fixture": (0, 0, 0, 0),
    "isolated_fixture": (0, 0, 0, 0),
    # tests
    "TestParent": (2, 0, 0, 0),
    "test_failure": (0, 0, 1, 0),
    "test_parameterized": (3, 0, 0, 0),
    "test_parameterized_collected": (2, 0, 0, 0),
    "test_sanity": (1, 0, 0, 0),
    "test_skip": (0, 1, 0, 0),
    "test_using_var_in_scope": (3, 0, 0, 0),
    "test_using_var_in_toplevel": (3, 0, 0, 0),
    # Fixtures - these now work with fixture preservation
    "test_uses_scoped_fixture": (1, 0, 0, 0),
    "test_parametrize_with_scoped_fixture": (2, 0, 0, 0),
    "TestWithClassFixture": (1, 0, 0, 0),
    "TestClassDefinitionWithFixtures": (3, 0, 0, 0),
    "test_uses_top_level_fixture": (1, 0, 0, 0),
    "test_parametrize_with_toplevel_fixture": (2, 0, 0, 0),
    "test_uses_function_fixture": (1, 0, 0, 0),
    # Fixture dependency chain test
    "base_fixture": (0, 0, 0, 0),  # fixture, not a test
    "dependent_fixture": (0, 0, 0, 0),  # fixture, not a test
    "test_fixture_dependency_chain": (1, 0, 0, 0),
    # Null cases - fixture not in scope / doesn't exist (errors)
    "test_cross_cell_fixture_fails": (0, 0, 0, 1),
    "test_missing_fixture": (0, 0, 0, 1),
}

_ISOLATION_DEFS = {"test_cross_cell_fixture_fails", "test_missing_fixture"}


@pytest.fixture(scope="module")
def notebook_env() -> tuple[
    type[_app_type], dict[str, object], Path, type[_run_pytest_type], set[str]
]:
    from marimo._ast.names import SETUP_CELL_NAME, TOPLEVEL_CELL_PREFIX
    from marimo._runtime.pytest import run_pytest
    from tests._runtime.script_data.contains_tests import app

    _, lcls = app.run()
    lcls = dict(lcls)
    path = Path(__file__).parent / "script_data/contains_tests.py"

    # Notebook-global defs (setup + top-level), normally resolved from the live
    # kernel graph; the script-mode `app.run()` above has no kernel context, so
    # compute them here and thread them through to `run_pytest`.
    global_defs: set[str] = set()
    for cid, cell in app._cell_manager.valid_cells():
        if str(cid) == SETUP_CELL_NAME or cell._name.startswith(
            TOPLEVEL_CELL_PREFIX
        ):
            global_defs |= cell._cell.defs

    # Turn off for recursion guard
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ["PYTEST_CURRENT_TEST"] = ""
    del os.environ["PYTEST_CURRENT_TEST"]
    # Give time for env changes to sync (helps with race conditions on Windows)
    asyncio.run(asyncio.sleep(0.1))

    yield app, lcls, path, run_pytest, global_defs

    if previous:
        os.environ["PYTEST_CURRENT_TEST"] = previous
    else:
        os.environ.pop("PYTEST_CURRENT_TEST", None)


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_batched_cells(notebook_env):
    """Batch all non-isolation cells into a single run_pytest call."""
    app, lcls, path, run_pytest, global_defs = notebook_env

    batch_defs: set[str] = set()
    batch_expected = [0, 0, 0, 0]  # passed, skipped, failed, errors
    for cell in app._cell_manager.cells():
        if cell and cell.__test__ and not (cell.defs & _ISOLATION_DEFS):
            batch_defs.update(cell.defs)
            for d in cell.defs:
                for i, v in enumerate(_DEF_COUNT[d]):
                    batch_expected[i] += v

    response = run_pytest(
        defs=batch_defs,
        lcls=lcls,
        notebook_path=path,
        global_defs=global_defs,
    )
    assert (
        response.passed,
        response.skipped,
        response.failed,
        response.errors,
    ) == tuple(batch_expected), response.output
    assert response.total == 28


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_isolation_cells(notebook_env):
    """Isolation tests run separately to verify fixture scoping errors."""
    app, lcls, path, run_pytest, global_defs = notebook_env

    total = 0
    for cell in app._cell_manager.cells():
        if cell and cell.__test__ and (cell.defs & _ISOLATION_DEFS):
            response = run_pytest(
                defs=cell.defs,
                lcls=lcls,
                notebook_path=path,
                global_defs=global_defs,
            )
            expected = tuple(
                map(
                    sum, zip(*[_DEF_COUNT[d] for d in cell.defs], strict=False)
                )
            )
            assert (
                response.passed,
                response.skipped,
                response.failed,
                response.errors,
            ) == expected, response.output
            total += response.total
    assert total == 2


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_live_collection_ignores_stale_disk(tmp_path) -> None:
    """Reactive collection reads the kernel's live globals, not the on-disk
    notebook, so unsaved edits are picked up without racing the save (#4797):
    new parametrize values, added tests, and renamed tests all take effect
    while the file on disk is deliberately stale.
    """
    import marimo
    from marimo._runtime.pytest import run_pytest

    app = marimo.App()

    @app.cell
    def _():
        import pytest

        return (pytest,)

    @app.cell
    def _(pytest):
        # Live: 3 param rows (edited/added a row), an added test, a renamed one.
        @pytest.mark.parametrize(("a", "b"), [(1, 2), (3, 4), (9, 9)])
        def test_values(a, b):
            assert a <= b

        def test_added():
            assert True

        def test_renamed_target():
            assert True

        return

    _, lcls = app.run()
    lcls = dict(lcls)
    defs = {"test_values", "test_added", "test_renamed_target"}

    # On-disk file is stale: one param row, the pre-rename name, no added test.
    stale = tmp_path / "notebook.py"
    stale.write_text(
        "import marimo\n"
        "app = marimo.App()\n\n"
        "@app.cell\n"
        "def _():\n"
        "    import pytest\n"
        "    return (pytest,)\n\n"
        "@app.cell\n"
        "def _(pytest):\n"
        "    @pytest.mark.parametrize(('a', 'b'), [(1, 2)])\n"
        "    def test_values(a, b):\n"
        "        assert a <= b\n"
        "    def test_old_name():\n"
        "        assert True\n"
        "    return\n"
    )

    # Recursion guard: we are invoking pytest from within pytest.
    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    asyncio.run(asyncio.sleep(0.1))
    try:
        result = run_pytest(defs=defs, lcls=lcls, notebook_path=stale)
    finally:
        if previous:
            os.environ["PYTEST_CURRENT_TEST"] = previous

    # 3 live param rows + test_added + test_renamed_target = 5, all passing.
    # The stale disk file (one row, test_old_name) is never read.
    assert (result.passed, result.failed, result.errors) == (5, 0, 0), (
        result.output
    )
    assert "test_renamed_target" in result.output
    assert "test_old_name" not in result.output


@pytest.mark.skipif(sys.platform == "win32", reason="Fails on Windows CI")
def test_offline_collection_inside_marimo_package() -> None:
    """Plain `pytest notebook.py` must collect multi-def cells, classes, and
    fixture-using tests even when the notebook lives inside the marimo package.

    `process_for_pytest` injects the generated MarimoTestBlock stub into the
    notebook's own module frame; an earlier "first frame not under marimo/"
    heuristic skipped that frame for notebooks inside the package (e.g.
    marimo/_smoke_tests/*), silently dropping every test in such cells.
    """
    import subprocess

    import marimo

    notebook = """
import marimo
app = marimo.App()

with app.setup:
    import pytest


@app.cell
def _():
    @pytest.fixture
    def my_fixture():
        return 7

    def test_uses_fixture(my_fixture):
        assert my_fixture == 7

    @pytest.mark.parametrize("x", [1, 2])
    def test_param(x):
        assert x > 0
    return


if __name__ == "__main__":
    app.run()
"""
    # The bug only triggers when the notebook path is inside the marimo package.
    pkg_dir = Path(marimo.__file__).parent / "_smoke_tests"
    nb = pkg_dir / f"_offline_collect_probe_{os.getpid()}.py"
    nb.write_text(notebook)
    # Mimic a standalone CLI run: the inherited PYTEST_CURRENT_TEST (set by the
    # outer pytest) would otherwise disable marimo's pytest test-rewrite in the
    # child during collection.
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(nb),
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:inline_snapshot",
            ],
            capture_output=True,
            text=True,
            cwd=Path(marimo.__file__).parent.parent,
            env=env,
        )
    finally:
        nb.unlink(missing_ok=True)

    out = proc.stdout + proc.stderr
    # Sanitize the pid-suffixed filename and timing, which vary per run.
    out = re.sub(r"_offline_collect_probe_\d+", "_offline_collect_probe", out)
    out = re.sub(r"in [\d.]+s", "in Ns", out)
    snapshot("offline_collection_inside_marimo_package.txt", out)


def test_pytest_result_summary_includes_xfail() -> None:
    from marimo._runtime.pytest import MarimoPytestResult

    result = MarimoPytestResult(
        passed=2, failed=1, errors=0, skipped=1, xfailed=3, xpassed=1
    )
    assert result.total == 8
    assert "XFailed: 3" in result.summary
    assert "XPassed: 1" in result.summary


def test_offline_notebook_location(tmp_path: Path) -> None:
    import subprocess

    notebook_dir = tmp_path / "notebooks"
    notebook_dir.mkdir()
    notebook = notebook_dir / "test_location.py"
    notebook.write_text(
        """
import marimo
app = marimo.App()

with app.setup:
    import pytest

@app.cell
def imports():
    import marimo as mo
    from pathlib import Path
    return mo, Path

@app.cell
def location(mo):
    directory = mo.notebook_dir()
    return (directory,)

@app.cell
def test_cell_location(Path, directory, mo):
    assert directory == Path(__file__).parent
    assert mo.notebook_location() == directory
    assert directory.name == "notebooks"

@app.cell
def _(Path, directory, mo):
    @pytest.fixture
    def location_fixture():
        assert mo.notebook_dir() == Path(__file__).parent
        return mo.notebook_location()

    def test_location(location_fixture):
        assert mo.notebook_dir() == directory == location_fixture
        assert directory.name == "notebooks"

    @pytest.mark.parametrize("change_cwd", [False, True])
    def test_location_after_chdir(change_cwd, monkeypatch, tmp_path):
        if change_cwd:
            monkeypatch.chdir(tmp_path)
        assert mo.notebook_dir() == Path(__file__).parent
        assert mo.app_meta().mode == "test"

    @pytest.mark.xfail(raises=ValueError, strict=True)
    def test_failure():
        assert mo.notebook_dir() == Path(__file__).parent
        raise ValueError("expected failure")

    @pytest.mark.asyncio
    async def test_async_location():
        import asyncio
        await asyncio.sleep(0)
        assert mo.notebook_location() == Path(__file__).parent
        assert directory.name == "notebooks"

    class TestLocation:
        def test_location(self):
            assert mo.notebook_dir() == Path(__file__).parent
            assert directory.name == "notebooks"

def test_context_restored():
    from pathlib import Path
    from marimo._runtime.context import runtime_context_installed
    assert not runtime_context_installed()
    assert marimo.notebook_dir() == Path.cwd()
    assert marimo.app_meta().mode == "test"
"""
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(notebook),
            "-q",
            "-p",
            "no:inline_snapshot",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "7 passed, 1 xfailed" in out


def test_pytest_result_summary_omits_zero_xfail() -> None:
    from marimo._runtime.pytest import MarimoPytestResult

    result = MarimoPytestResult(passed=5, failed=0, errors=0, skipped=0)
    assert "XFailed" not in result.summary
    assert "XPassed" not in result.summary


@pytest.mark.parametrize("failure", [None, "cell", "test"])
def test_sync_hook_closes_event_loop(monkeypatch, failure: str | None) -> None:
    from marimo._ast.pytest import _make_hook

    loop = asyncio.new_event_loop()
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: loop)

    def test_function():
        if failure == "test":
            raise ValueError("test failed")
        return "test result"

    async def run_cell():
        await asyncio.sleep(0)
        if failure == "cell":
            raise ValueError("cell failed")
        return None, {"test_function": test_function}

    hook = _make_hook("test_function", run_cell, __file__)
    try:
        if failure:
            with pytest.raises(ValueError, match=f"{failure} failed"):
                hook()
        else:
            assert hook() == "test result"
        assert loop.is_closed()
    finally:
        loop.close()


def test_rerun_keeps_lazily_imported_modules(tmp_path, monkeypatch) -> None:
    """Installed modules first imported during a run survive to the next run.

    `run_pytest` restores `sys.modules` after each run so project-local
    imports (conftest, helpers) reload with edits. Installed packages must be
    kept: evicting one that a test imported lazily (e.g. `torch.manual_seed`
    -> `torch._dynamo` -> `TORCH_LIBRARY` registration) re-executes its body
    next run, while state outside the Python module (C++ dispatcher) persists,
    raising "Only a single TORCH_LIBRARY can be used to register the
    namespace".
    """
    import marimo
    from marimo._runtime.pytest import run_pytest
    from marimo._runtime.reload import autoreload

    # Stand in for an installed package: extend the stdlib/site-packages
    # roots so `fake_torch` classifies as non-user code.
    roots = autoreload._non_user_module_roots()
    installed = os.path.normcase(os.path.realpath(tmp_path / "installed"))
    monkeypatch.setattr(
        autoreload,
        "_non_user_module_roots",
        lambda: roots + (installed + os.sep,),
    )
    (tmp_path / "installed").mkdir()
    pkg = tmp_path / "installed" / "fake_torch"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from . import _C\n\n"
        "def seed():\n"
        "    # Lazy submodule import, as in torch._compile\n"
        "    import fake_torch._dynamo  # noqa: F401\n"
    )
    # Registry state outliving the Python module, like the C++ dispatcher.
    (pkg / "_C.py").write_text(
        "REGISTERED: set[str] = set()\n\n"
        "def dispatch_library(ns):\n"
        "    if ns in REGISTERED:\n"
        "        raise RuntimeError(f'Only a single TORCH_LIBRARY for {ns}')\n"
        "    REGISTERED.add(ns)\n"
    )
    (pkg / "_dynamo.py").write_text(
        "from . import _C\n\n_C.dispatch_library('_inductor_test')\n"
    )
    # Project-local helper, imported lazily by the test.
    (tmp_path / "local_helper.py").write_text("VALUE = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path / "installed"))
    monkeypatch.syspath_prepend(str(tmp_path))

    app = marimo.App()

    @app.cell
    def _():
        import fake_torch  # type: ignore[import-not-found]

        return (fake_torch,)

    @app.cell
    def _(fake_torch):
        def test_seed():
            import local_helper  # type: ignore[import-not-found]

            fake_torch.seed()
            assert local_helper.VALUE == 1

        return

    notebook = tmp_path / "notebook.py"
    notebook.write_text("import marimo\napp = marimo.App()\n")

    previous = os.environ.get("PYTEST_CURRENT_TEST", "")
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    asyncio.run(asyncio.sleep(0.1))
    try:
        _, lcls = app.run()
        lcls = dict(lcls)
        results = [
            run_pytest(defs={"test_seed"}, lcls=lcls, notebook_path=notebook)
            for _ in range(2)
        ]
        dynamo_kept = "fake_torch._dynamo" in sys.modules
        helper_kept = "local_helper" in sys.modules
    finally:
        if previous:
            os.environ["PYTEST_CURRENT_TEST"] = previous
        for name in [
            n
            for n in sys.modules
            if n.startswith("fake_torch") or n == "local_helper"
        ]:
            del sys.modules[name]

    for run, result in enumerate(results, start=1):
        assert (result.passed, result.failed, result.errors) == (1, 0, 0), (
            f"run {run}: {result.output}"
        )
    # Installed modules survive the run; project-local ones are evicted so
    # edits are picked up on the next run.
    assert dynamo_kept
    assert not helper_kept
