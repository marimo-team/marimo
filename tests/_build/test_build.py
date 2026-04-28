# Copyright 2026 Marimo. All rights reserved.
"""End-to-end build pipeline tests.

Requires the `test-optional` group: polars + duckdb + sqlglot.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from marimo._build import build_notebook

pytest.importorskip("polars")
pytest.importorskip("duckdb")
pytest.importorskip("sqlglot")


FIXTURE = Path(__file__).parent / "fixtures" / "example_notebook.py"


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy the fixture into a fresh tmp dir so each test mutates its own."""
    target = tmp_path / FIXTURE.name
    target.write_text(FIXTURE.read_text())
    return target


def test_build_emits_artifacts_and_compiled_notebook(tmp_path: Path) -> None:
    notebook = _copy_fixture(tmp_path)
    result = build_notebook(notebook)

    # Output dir defaults to __marimo_build__/<stem>/ next to the source.
    expected_dir = tmp_path / "__marimo_build__" / "example_notebook"
    assert result.output_dir == expected_dir
    assert result.compiled_notebook == expected_dir / "example_notebook.py"
    assert result.compiled_notebook.exists()
    assert (expected_dir / ".manifest.json").exists()

    # Named cells with no UI dependency get artifacts:
    assert result.status_for("customers") == "compiled"
    assert result.status_for("orders_enriched") == "compiled"
    assert result.status_for("settings") == "compiled"

    # UI cell and its descendant stay non-compilable.
    assert result.status_for("category") == "kept"
    assert result.status_for("filtered") == "kept"

    # Anonymous cells: _users feeds only orders_enriched (now a loader),
    # so it can be elided. _imports defines `mo` which the SQL loader
    # for customers/orders_enriched still needs, so it stays.
    assert result.status_for("_users") == "elided"
    assert result.status_for("_imports") == "kept"

    # Three named cells produce four artifacts (3 parquet + 1 json).
    artifact_names = sorted(p.name for p in result.artifacts)
    assert any(
        n.startswith("customers-") and n.endswith(".parquet")
        for n in artifact_names
    )
    assert any(
        n.startswith("orders_enriched-") and n.endswith(".parquet")
        for n in artifact_names
    )
    assert any(
        n.startswith("settings-") and n.endswith(".json")
        for n in artifact_names
    )


def test_compiled_notebook_runs_and_produces_same_data(
    tmp_path: Path,
) -> None:
    notebook = _copy_fixture(tmp_path)
    result = build_notebook(notebook)

    # Run the compiled notebook as a script and import its `app`.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                f"import sys, importlib.util\n"
                f"spec = importlib.util.spec_from_file_location("
                f"'compiled', r'{result.compiled_notebook}')\n"
                f"mod = importlib.util.module_from_spec(spec)\n"
                f"spec.loader.exec_module(mod)\n"
                f"_, defs = mod.app.run("
                f"defs={{'category': type('UI', (), {{'value': 'alice'}})()}})\n"
                f"print('OK',"
                f" 'name' in defs.get('customers').columns,"
                f" defs.get('settings'))\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"compiled notebook failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert proc.stdout.startswith("OK True"), proc.stdout


def test_rebuild_is_no_op_when_unchanged(tmp_path: Path) -> None:
    notebook = _copy_fixture(tmp_path)
    first = build_notebook(notebook)
    first_mtimes = {p: p.stat().st_mtime_ns for p in first.artifacts}

    second = build_notebook(notebook)
    for path in second.artifacts:
        # Same path, unchanged mtime: not rewritten.
        assert path in first_mtimes
        assert path.stat().st_mtime_ns == first_mtimes[path], path
    # All compilable cells should report "cached" the second time.
    cached = {e.name for e in second.cell_statuses if e.status == "cached"}
    assert {"customers", "orders_enriched", "settings"} <= cached


def test_source_change_triggers_rematerialize_and_gc(
    tmp_path: Path,
) -> None:
    notebook = _copy_fixture(tmp_path)
    first = build_notebook(notebook)
    customers_v1 = next(
        p for p in first.artifacts if p.name.startswith("customers-")
    )

    # Modify the customers cell so its hash (and therefore filename) changes.
    src = notebook.read_text().replace(
        "SELECT 1 AS id, 'alice' AS name",
        "SELECT 2 AS id, 'bob' AS name",
    )
    notebook.write_text(src)

    second = build_notebook(notebook)
    customers_v2 = next(
        p for p in second.artifacts if p.name.startswith("customers-")
    )
    assert customers_v2.name != customers_v1.name
    # Old artifact deleted by stale-artifact GC.
    assert customers_v1 in second.deleted
    assert not customers_v1.exists()
    # Downstream artifact also re-hashed (parent change cascades).
    enriched_v1 = next(
        p for p in first.artifacts if p.name.startswith("orders_enriched-")
    )
    enriched_v2 = next(
        p for p in second.artifacts if p.name.startswith("orders_enriched-")
    )
    assert enriched_v2.name != enriched_v1.name


def test_force_rewrites_existing_artifacts(tmp_path: Path) -> None:
    notebook = _copy_fixture(tmp_path)
    first = build_notebook(notebook)
    first_mtimes = {p: p.stat().st_mtime_ns for p in first.artifacts}

    # Sleep a tiny bit so mtime can advance.
    import time

    time.sleep(0.01)

    second = build_notebook(notebook, force=True)
    for path in second.artifacts:
        assert path in first_mtimes
        assert path.stat().st_mtime_ns > first_mtimes[path], path


def test_setup_cell_globals_are_available_to_compilable_cells(
    tmp_path: Path,
) -> None:
    """Notebooks that import via ``with app.setup:`` must still build.

    ``load_app`` builds the App from IR (it doesn't import the file as
    a Python module), so the setup cell's ``with`` block never actually
    runs. The build pipeline has to execute the setup cell body itself,
    or every downstream cell will fail with ``NameError: mo``.
    """
    notebook = tmp_path / "setup_cell.py"
    notebook.write_text(
        "import marimo\n"
        '__generated_with = "0.0.0"\n'
        "app = marimo.App()\n"
        "\n"
        "with app.setup:\n"
        "    import marimo as mo\n"
        "\n"
        "@app.cell\n"
        "def customers():\n"
        "    customers = mo.sql('SELECT 1 AS id')\n"
        "    return (customers,)\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    app.run()\n"
    )
    result = build_notebook(notebook)
    assert result.status_for("customers") == "compiled"
    assert result.status_for("setup") == "setup"


def test_runtime_error_aborts_build(tmp_path: Path) -> None:
    """A cell that raises must fail the build, not silently demote.

    Marimo wraps cell exceptions in ``MarimoRuntimeException``
    (a ``BaseException`` subclass). ``BuildExecutionError`` should
    surface the cell name and chain the original cause.
    """
    from marimo._build.runner import BuildExecutionError

    notebook = tmp_path / "boom.py"
    notebook.write_text(
        "import marimo\n"
        '__generated_with = "0.0.0"\n'
        "app = marimo.App()\n"
        "\n"
        "@app.cell\n"
        "def _imports():\n"
        "    import marimo as mo\n"
        "    return (mo,)\n"
        "\n"
        "@app.cell\n"
        "def boom():\n"
        "    boom = 1 / 0\n"
        "    return (boom,)\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    app.run()\n"
    )
    with pytest.raises(BuildExecutionError, match="boom") as exc_info:
        build_notebook(notebook)
    assert isinstance(exc_info.value.__cause__, ZeroDivisionError)


def test_cell_statuses_preserve_anonymous_cells(tmp_path: Path) -> None:
    """A notebook full of ``_``-named cells doesn't collapse statuses.

    Also locks in the display-name fallback: anonymous cells with
    defs should surface those defs, and display-only cells should
    surface their last expression rather than ``"_"``.
    """
    notebook = tmp_path / "anonymous.py"
    notebook.write_text(
        "import marimo\n"
        '__generated_with = "0.0.0"\n'
        "app = marimo.App()\n"
        "\n"
        "@app.cell\n"
        "def _():\n"
        "    a = 1\n"
        "    return (a,)\n"
        "\n"
        "@app.cell\n"
        "def _(a):\n"
        "    b = a + 1\n"
        "    return (b,)\n"
        "\n"
        "@app.cell\n"
        "def _(b):\n"
        "    print(b)\n"
        "    return\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    app.run()\n"
    )
    result = build_notebook(notebook)
    rows = [(e.status, e.display_name) for e in result.cell_statuses]
    # Three ``_`` cells, three distinct outcomes preserved in order;
    # display name falls back to defs / last expression so the user
    # can read the build output even though every cell is named "_".
    assert rows == [
        ("elided", "a"),
        ("compiled", "b"),
        ("kept", "print(b)"),
    ]


def test_progress_callback_streams_phases_and_cells(tmp_path: Path) -> None:
    """Every phase boundary, executed cell, and the final ``done`` event fires.

    The exact set of cells we run depends on the fixture, but we lock
    in the *shape* of the stream: phases bracket the work, cells fire
    in execute order, and the terminal event is always ``done``.
    """
    from marimo._build.events import (
        BuildDone,
        CellExecuted,
        CellExecuting,
        PhaseFinished,
        PhaseStarted,
    )

    notebook = _copy_fixture(tmp_path)
    events: list[object] = []
    build_notebook(notebook, progress_callback=events.append)

    phases_started = [e.phase for e in events if isinstance(e, PhaseStarted)]
    phases_finished = [e.phase for e in events if isinstance(e, PhaseFinished)]
    assert phases_started == [
        "classify",
        "execute",
        "plan",
        "persist",
        "codegen",
        "gc",
    ]
    assert phases_started == phases_finished

    # Every executing event has a matching executed event in order.
    executing = [e.name for e in events if isinstance(e, CellExecuting)]
    executed = [e.name for e in events if isinstance(e, CellExecuted)]
    assert executing == executed
    # All executed cells have non-negative timing.
    for e in events:
        if isinstance(e, CellExecuted):
            assert e.elapsed_ms >= 0

    # The terminal event is the BuildDone summary.
    assert isinstance(events[-1], BuildDone)


def test_should_cancel_aborts_between_cells(tmp_path: Path) -> None:
    """Setting the cancel flag mid-flight raises ``BuildCancelled``."""
    from marimo._build.events import CellExecuting
    from marimo._build.runner import BuildCancelled

    notebook = _copy_fixture(tmp_path)
    cancel = False

    def progress(event: object) -> None:
        nonlocal cancel
        # Cancel as soon as the first cell starts executing.
        if isinstance(event, CellExecuting):
            cancel = True

    with pytest.raises(BuildCancelled):
        build_notebook(
            notebook,
            progress_callback=progress,
            should_cancel=lambda: cancel,
        )


def test_manifest_indexes_artifacts_by_def_name(tmp_path: Path) -> None:
    """The manifest is a ``{def_name: {file, kind}}`` map, not a flat list."""
    import json

    notebook = _copy_fixture(tmp_path)
    result = build_notebook(notebook)
    manifest = json.loads((result.output_dir / ".manifest.json").read_text())

    assert manifest["compiled"] == "example_notebook.py"
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    # Lookup by def name; the kind is canonical (not parsed from extension).
    assert artifacts["customers"]["kind"] == "dataframe"
    assert artifacts["customers"]["file"].startswith("customers-")
    assert artifacts["customers"]["file"].endswith(".parquet")
    assert artifacts["settings"]["kind"] == "json"
    assert artifacts["settings"]["file"].endswith(".json")


def test_helper_cell_only_emits_referenced_helpers(tmp_path: Path) -> None:
    """The helper cell emits exactly the loader functions in use.

    The fixture has one Python JSON loader (``settings``) and several
    SQL parquet loaders, but no Python parquet loader — so
    ``marimo_load_parquet`` should be absent from the compiled notebook.
    """
    notebook = _copy_fixture(tmp_path)
    result = build_notebook(notebook)
    source = result.compiled_notebook.read_text()

    assert "def marimo_artifact_path" in source
    assert "def marimo_load_json" in source
    assert "def marimo_load_parquet" not in source
    # And no module-level Path import either.
    assert "marimo_build_path" not in source


def test_non_persistable_cell_does_not_cascade(tmp_path: Path) -> None:
    """Non-persistable defs only force *their own* cell verbatim.

    A descendant whose own value is persistable is still compilable —
    the downstream cell ran successfully at build time using the
    upstream lambda, and the loader replaces the result directly.
    """
    notebook = tmp_path / "no_cascade.py"
    notebook.write_text(
        "import marimo\n"
        '__generated_with = "0.0.0"\n'
        "app = marimo.App()\n"
        "\n"
        "@app.cell\n"
        "def _imports():\n"
        "    import marimo as mo\n"
        "    return (mo,)\n"
        "\n"
        "@app.cell\n"
        "def cant_serialize():\n"
        "    cant_serialize = lambda x: x  # not parquet, not JSON\n"
        "    return (cant_serialize,)\n"
        "\n"
        "@app.cell\n"
        "def downstream(cant_serialize):\n"
        "    downstream = cant_serialize(1)\n"
        "    return (downstream,)\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    app.run()\n"
    )
    result = build_notebook(notebook)
    # `cant_serialize` itself can't be a loader — it stays verbatim.
    assert result.status_for("cant_serialize") == "kept"
    # `downstream` produced an int, which IS persistable, so it
    # becomes a loader. At notebook-load time the verbatim
    # `cant_serialize` cell still runs but downstream just reads its
    # JSON, so the lambda is bound but unused.
    assert result.status_for("downstream") == "compiled"
    assert any(
        p.name.startswith("downstream-") and p.suffix == ".json"
        for p in result.artifacts
    )
