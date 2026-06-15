# Copyright 2026 Marimo. All rights reserved.
"""Tests for WASM compatibility lint rules (MW001, MW002, MW003)."""

from __future__ import annotations

import json
from textwrap import dedent, indent
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from typing_extensions import Self

from marimo._ast.parse import parse_notebook
from marimo._lint.diagnostic import Severity
from marimo._utils.requests import Response
from tests._lint.utils import lint_notebook

TEST_FILE = "tests/_lint/test_files/wasm_incompatible.py"


def _load_notebook():
    with open(TEST_FILE) as f:
        code = f.read()
    return parse_notebook(code, filepath=TEST_FILE), code


def _lint_cell(source: str, select: list[str]):
    return _lint_cells([source], select)


def _lint_cells(sources: list[str], select: list[str]):
    cells = []
    for source in sources:
        body = indent(dedent(source).strip(), "    ")
        cells.append(
            f"""
@app.cell
def _():
{body}
    return
"""
        )

    contents = f"""import marimo

__generated_with = "0.0.0"
app = marimo.App()

{"".join(cells)}

if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(contents, filepath="test.py")
    return lint_notebook(notebook, contents, lint_config={"select": select})


class TestWasmRulesOffByDefault:
    """MW rules should not fire without explicit --select MW."""

    def test_no_wasm_diagnostics_by_default(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(notebook, contents)
        assert not any(d.code.startswith("MW") for d in diagnostics)


class TestMW001IncompatibleImports:
    """MW001: Importing modules unavailable in WASM/Pyodide."""

    def test_subprocess_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        codes = [d.code for d in diagnostics]
        messages = [d.message for d in diagnostics]
        assert "MW001" in codes
        assert any("subprocess" in m for m in messages)

    def test_multiprocessing_not_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = [d.message for d in diagnostics]
        assert not any("multiprocessing" in m for m in messages)

    def test_unsupported_multiprocessing_imports_flagged(self):
        diagnostics = _lint_cell(
            """
            from multiprocessing import Pipe, Manager, Queue
            from multiprocessing.context import ForkProcess, Process
            from multiprocessing.pool import Pool, ThreadPool
            from multiprocessing.queues import JoinableQueue, Queue
            import multiprocessing.shared_memory
            """,
            ["MW001"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe" in m for m in messages)
        assert any("multiprocessing.Manager" in m for m in messages)
        assert any(
            "multiprocessing.context.ForkProcess" in m for m in messages
        )
        assert any("multiprocessing.pool.ThreadPool" in m for m in messages)
        assert any(
            "multiprocessing.queues.JoinableQueue" in m for m in messages
        )
        assert any("multiprocessing.shared_memory" in m for m in messages)
        assert not any("multiprocessing.Queue" in m for m in messages)
        assert not any(
            "multiprocessing.context.Process" in m for m in messages
        )
        assert not any("multiprocessing.pool.Pool" in m for m in messages)
        assert not any("multiprocessing.queues.Queue" in m for m in messages)

    def test_relative_multiprocessing_imports_not_flagged(self):
        diagnostics = _lint_cell(
            """
            from .multiprocessing import Pipe
            from .multiprocessing.pool import ThreadPool
            """,
            ["MW001"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe" in m for m in messages)
        assert not any(
            "multiprocessing.pool.ThreadPool" in m for m in messages
        )

    def test_pdb_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("pdb" in m for m in messages)

    def test_pydecimal_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("pydecimal" in m for m in messages)

    def test_severity_is_wasm(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        for d in diagnostics:
            assert d.severity == Severity.WASM

    def test_safe_imports_not_flagged(self):
        """Standard safe imports like os should not be flagged."""
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW001"]}
        )
        messages = " ".join(d.message for d in diagnostics)
        # os is importable in Pyodide. Only specific os.* calls are bad.
        assert "Module 'os'" not in messages


class TestMW002UnsafeSystemCalls:
    """MW002: System calls that fail in WASM/Pyodide."""

    def test_os_system_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("os.system()" in m for m in messages)

    def test_breakpoint_flagged(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        messages = [d.message for d in diagnostics]
        assert any("breakpoint()" in m for m in messages)

    def test_breakpoint_shadow_not_flagged(self):
        diagnostics = _lint_cell(
            """
            def callback(breakpoint):
                breakpoint()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]
        assert not any("breakpoint()" in m for m in messages)

    def test_os_exec_spawn_import_aliases_flagged(self):
        diagnostics = _lint_cell(
            """
            from os import execl, spawnv

            execl("/bin/echo", "echo")
            spawnv(0, "/bin/echo", ["echo"])
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.execl()" in m for m in messages)
        assert any("os.spawnv()" in m for m in messages)

    def test_unsupported_multiprocessing_calls_flagged(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing
            import multiprocessing as mp
            import multiprocessing.pool
            import multiprocessing.context as mp_context
            from multiprocessing import Pipe as imported_pipe
            from multiprocessing import get_context as imported_get_context
            from multiprocessing import pool as imported_pool
            from multiprocessing.pool import ThreadPool as ImportedThreadPool
            from multiprocessing.queues import JoinableQueue

            multiprocessing.Manager()
            multiprocessing.Pipe()
            multiprocessing.Queue()
            mp.Pipe()
            multiprocessing.pool.ThreadPool()
            mp_context.ForkProcess()
            mp_context.Process()
            imported_pipe()
            imported_pool.ThreadPool()
            ImportedThreadPool()
            JoinableQueue()
            mp.get_context("fork")
            mp.get_context("spawn")
            mp.set_start_method(method="fork")
            imported_get_context("forkserver")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Manager()" in m for m in messages)
        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert any("multiprocessing.pool.ThreadPool()" in m for m in messages)
        assert any(
            "multiprocessing.context.ForkProcess()" in m for m in messages
        )
        assert any(
            "multiprocessing.queues.JoinableQueue()" in m for m in messages
        )
        assert any(
            "multiprocessing.get_context('fork')" in m for m in messages
        )
        assert any(
            "multiprocessing.get_context('forkserver')" in m for m in messages
        )
        assert any(
            "multiprocessing.set_start_method('fork')" in m for m in messages
        )
        assert not any("multiprocessing.Queue()" in m for m in messages)
        assert not any(
            "multiprocessing.context.Process()" in m for m in messages
        )
        assert not any(
            "multiprocessing.get_context('spawn')" in m for m in messages
        )

    def test_multiprocessing_aliases_resolve_across_cells(self):
        diagnostics = _lint_cells(
            [
                """
                import multiprocessing as mp
                from multiprocessing import get_context
                """,
                """
                mp.Pipe()
                get_context("fork")
                mp.get_context("spawn")
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert any(
            "multiprocessing.get_context('fork')" in m for m in messages
        )
        assert not any(
            "multiprocessing.get_context('spawn')" in m for m in messages
        )

    def test_multiprocessing_aliases_respect_local_shadowing(self):
        diagnostics = _lint_cells(
            [
                """
                import multiprocessing as mp
                from multiprocessing import Pipe, get_context
                """,
                """
                def parameter_shadow(mp, Pipe, get_context):
                    mp.Pipe()
                    Pipe()
                    get_context("fork")

                def assignment_shadow():
                    mp = object()
                    Pipe = lambda: None
                    get_context = lambda method: None
                    mp.Pipe()
                    Pipe()
                    get_context("fork")
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)
        assert not any(
            "multiprocessing.get_context('fork')" in m for m in messages
        )

    def test_multiprocessing_local_import_aliases_flagged(self):
        diagnostics = _lint_cell(
            """
            def local_imports():
                import multiprocessing as mp
                from multiprocessing import get_context

                mp.Pipe()
                get_context("fork")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert any(
            "multiprocessing.get_context('fork')" in m for m in messages
        )

    def test_relative_import_aliases_not_treated_as_stdlib(self):
        diagnostics = _lint_cell(
            """
            from .os import system
            from .multiprocessing import Pipe

            system()
            Pipe()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)
        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_relative_import_aliases_shadow_cross_cell_aliases(self):
        diagnostics = _lint_cells(
            [
                """
                from multiprocessing import Pipe
                """,
                """
                from .local import Pipe

                Pipe()
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_safe_root_multiprocessing_binding_suppresses_stdlib_fallback(
        self,
    ):
        diagnostics = _lint_cells(
            [
                """
                from . import multiprocessing
                """,
                """
                multiprocessing.Pipe()
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_later_safe_root_binding_suppresses_function_fallback(self):
        diagnostics = _lint_cells(
            [
                """
                def run():
                    multiprocessing.Pipe()
                """,
                """
                from . import multiprocessing
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_safe_import_rebinding_clears_unsafe_aliases(self):
        diagnostics = _lint_cell(
            """
            from os import system
            from safe import system
            system()

            from multiprocessing import Pipe
            import safe as Pipe
            Pipe()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)
        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_comprehension_targets_do_not_shadow_function_aliases(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing as mp

            def run():
                [mp for mp in ()]
                mp.Pipe()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)

    def test_comprehension_targets_shadow_inside_comprehension(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing as mp

            def run(values):
                [mp.Pipe() for mp in values]
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_class_scope_does_not_shadow_method_globals(self):
        diagnostics = _lint_cell(
            """
            import os

            class Runner:
                os = object()

                def run(self):
                    os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_class_body_bindings_shadow_class_body_calls(self):
        diagnostics = _lint_cell(
            """
            import os

            class Runner:
                os = object()
                os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)

    def test_class_name_not_bound_while_class_body_runs(self):
        diagnostics = _lint_cell(
            """
            import os

            class os:
                os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_class_name_shadows_method_globals_after_binding(self):
        diagnostics = _lint_cell(
            """
            import os

            class os:
                def run(self):
                    os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)

    def test_nested_class_name_in_class_does_not_shadow_method_globals(self):
        diagnostics = _lint_cell(
            """
            import os

            class Outer:
                class os:
                    def run(self):
                        os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_function_local_class_name_shadows_method_globals(self):
        diagnostics = _lint_cell(
            """
            import os

            def factory():
                class os:
                    def run(self):
                        os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)

    def test_function_parameter_annotations_are_checked(self):
        diagnostics = _lint_cell(
            """
            import os

            def positional(value: os.system("positional")):
                return value

            def keyword_only(*, value: os.system("keyword")):
                return value

            def variadic(
                *values: os.system("vararg"),
                **kwargs: os.system("kwarg"),
            ):
                return values, kwargs
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert sum("os.system()" in m for m in messages) == 4

    def test_value_less_annotations_do_not_clear_runtime_aliases(self):
        diagnostics = _lint_cell(
            """
            import os

            os: object
            os.system("module")

            class Runner:
                os: object
                os.system("class")

            def local_import():
                import os
                os: object
                os.system("function")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert sum("os.system()" in m for m in messages) == 3

    def test_function_value_less_annotation_blocks_global_alias(self):
        diagnostics = _lint_cell(
            """
            import os

            def run():
                os: object
                os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("os.system()" in m for m in messages)

    def test_value_less_annotation_target_expressions_are_checked(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing
            import os

            items = {}
            items[os.system("ls")]: int
            items[multiprocessing.Pipe()]: int
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)
        assert any("multiprocessing.Pipe()" in m for m in messages)

    def test_spawn_context_unsupported_factories_flagged(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing

            ctx = multiprocessing.get_context("spawn")
            ctx.Pipe()
            ctx.Manager()
            ctx.JoinableQueue()
            ctx.Lock()
            ctx.Queue()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.context.Pipe()" in m for m in messages)
        assert any("multiprocessing.context.Manager()" in m for m in messages)
        assert any(
            "multiprocessing.context.JoinableQueue()" in m for m in messages
        )
        assert any("multiprocessing.context.Lock()" in m for m in messages)
        assert not any(
            "multiprocessing.context.Queue()" in m for m in messages
        )

    def test_spawn_context_alias_resolves_across_cells(self):
        diagnostics = _lint_cells(
            [
                """
                import multiprocessing

                ctx = multiprocessing.get_context("spawn")
                """,
                """
                ctx.Pipe()
                ctx.Queue()
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.context.Pipe()" in m for m in messages)
        assert not any(
            "multiprocessing.context.Queue()" in m for m in messages
        )

    def test_chained_spawn_context_unsupported_factories_flagged(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing
            from multiprocessing import get_context

            multiprocessing.get_context("spawn").Pipe()
            get_context("spawn").Manager()
            multiprocessing.get_context("spawn").Queue()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.context.Pipe()" in m for m in messages)
        assert any("multiprocessing.context.Manager()" in m for m in messages)
        assert not any(
            "multiprocessing.context.Queue()" in m for m in messages
        )

    def test_multiprocessing_assignment_aliases_flagged(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing

            mp = multiprocessing
            pipe = multiprocessing.Pipe
            manager = mp.Manager

            mp.Pipe()
            mp.Queue()
            pipe()
            manager()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert any("multiprocessing.Manager()" in m for m in messages)
        assert not any("multiprocessing.Queue()" in m for m in messages)

    def test_multiprocessing_assignment_aliases_resolve_across_cells(self):
        diagnostics = _lint_cells(
            [
                """
                import multiprocessing

                mp = multiprocessing
                pipe = multiprocessing.Pipe
                """,
                """
                mp.Pipe()
                mp.Queue()
                pipe()
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert not any("multiprocessing.Queue()" in m for m in messages)

    def test_multiprocessing_destructured_assignment_aliases_flagged(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing

            pipe, queue = multiprocessing.Pipe, multiprocessing.Queue

            pipe()
            queue()
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert not any("multiprocessing.Queue()" in m for m in messages)

    def test_reassigned_call_aliases_are_flagged(self):
        diagnostics = _lint_cell(
            """
            from multiprocessing import Pipe, get_context

            pipe = Pipe
            gc = get_context

            pipe()
            gc("fork")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("multiprocessing.Pipe()" in m for m in messages)
        assert any(
            "multiprocessing.get_context('fork')" in m for m in messages
        )

    def test_conditional_rebinding_does_not_hide_later_unsafe_calls(self):
        diagnostics = _lint_cell(
            """
            import os

            if condition:
                os = object()
                os.system("branch")

            os.system("after")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_assignment_target_expressions_are_checked(self):
        diagnostics = _lint_cell(
            """
            import multiprocessing
            import os

            items = {}
            items[os.system("ls")] = "os"
            items[multiprocessing.Pipe()] = "pipe"
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)
        assert any("multiprocessing.Pipe()" in m for m in messages)

    def test_root_rebinding_clears_seeded_unsafe_aliases(self):
        diagnostics = _lint_cells(
            [
                """
                from multiprocessing import Pipe

                def safe_pipe():
                    return None

                Pipe = safe_pipe
                """,
                """
                Pipe()
                """,
            ],
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert not any("multiprocessing.Pipe()" in m for m in messages)

    def test_guarded_import_aliases_apply_after_branch(self):
        diagnostics = _lint_cell(
            """
            def run():
                try:
                    import os
                except ImportError:
                    return

                os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_loop_import_aliases_apply_after_loop(self):
        diagnostics = _lint_cell(
            """
            def run():
                for _ in (0,):
                    import os

                os.system("ls")
            """,
            ["MW002"],
        )
        messages = [d.message for d in diagnostics]

        assert any("os.system()" in m for m in messages)

    def test_severity_is_wasm(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        for d in diagnostics:
            assert d.severity == Severity.WASM

    def test_line_numbers_are_set(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW002"]}
        )
        for d in diagnostics:
            assert d.line > 0


class TestMW001AndMW002Together:
    """Both MW001 and MW002 should fire on the test file."""

    def test_combined_diagnostics(self):
        notebook, contents = _load_notebook()
        diagnostics = lint_notebook(
            notebook, contents, lint_config={"select": ["MW"]}
        )
        codes = {d.code for d in diagnostics}
        assert "MW001" in codes
        assert "MW002" in codes


_PEP723_NOTEBOOK = """# /// script
# requires-python = ">=3.11"
# dependencies = [{deps}]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
"""


def _fake_lockfile_response(packages: dict[str, str]) -> Response:
    """Build a fake pyodide-lock.json response for the given {name: version}."""
    payload = {
        "packages": {
            name: {
                "name": name,
                "version": version,
                "package_type": "package",
            }
            for name, version in packages.items()
        }
    }
    return Response(
        status_code=200,
        content=json.dumps(payload).encode("utf-8"),
        headers={},
    )


class _FakePypiResponse:
    """Stand-in for the urllib response used by `_has_wasm_compatible_wheel`."""

    def __init__(self, payload: dict[str, object]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class TestMW003IncompatiblePackages:
    """MW003: PEP 723 deps incompatible with WASM/Pyodide."""

    def _write_and_parse(self, tmp_path, deps: list[str]):
        nb_file = tmp_path / "nb.py"
        deps_literal = ", ".join(f'"{d}"' for d in deps)
        nb_file.write_text(_PEP723_NOTEBOOK.format(deps=deps_literal))
        contents = nb_file.read_text()
        notebook = parse_notebook(contents, filepath=str(nb_file))
        return notebook, contents

    def test_pyodide_listed_dep_not_flagged(self, monkeypatch, tmp_path):
        """Lockfile lookup short-circuits before the PyPI fetch."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        # _resolve_dep_tree walks importlib.metadata locally, so short-circuit
        # it so the test doesn't depend on the host env.
        monkeypatch.setattr(mod, "_resolve_dep_tree", lambda deps: deps)
        # Guard: PyPI must not be hit when the dep is already in the lockfile.
        mod._has_wasm_compatible_wheel.cache_clear()

        notebook, contents = self._write_and_parse(tmp_path, ["numpy"])
        with (
            patch(
                "marimo._pyodide.pyodide_constraints.requests.get",
                return_value=_fake_lockfile_response({"numpy": "2.0.2"}),
            ),
            patch(
                "marimo._lint.rules.wasm.incompatible_packages."
                "urllib.request.urlopen",
                side_effect=AssertionError(
                    "PyPI must not be queried for lockfile-listed packages"
                ),
            ),
        ):
            diagnostics = lint_notebook(
                notebook, contents, lint_config={"select": ["MW003"]}
            )
        assert not any(d.code == "MW003" for d in diagnostics)

    def test_dep_without_compatible_wheel_flagged(self, monkeypatch, tmp_path):
        """Non-lockfile dep whose PyPI release ships only native wheels fires MW003."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        monkeypatch.setattr(mod, "_resolve_dep_tree", lambda deps: deps)
        mod._has_wasm_compatible_wheel.cache_clear()

        notebook, contents = self._write_and_parse(tmp_path, ["jaxlib"])
        pypi_payload = {
            "urls": [
                {
                    "filename": "jaxlib-0.4.30-cp312-cp312-manylinux2014_x86_64.whl"
                }
            ]
        }
        with (
            patch(
                "marimo._pyodide.pyodide_constraints.requests.get",
                return_value=_fake_lockfile_response({}),
            ),
            patch(
                "marimo._lint.rules.wasm.incompatible_packages."
                "urllib.request.urlopen",
                return_value=_FakePypiResponse(pypi_payload),
            ),
        ):
            diagnostics = lint_notebook(
                notebook, contents, lint_config={"select": ["MW003"]}
            )
        mw003 = [d for d in diagnostics if d.code == "MW003"]
        assert len(mw003) == 1
        assert "jaxlib" in mw003[0].message
        assert mw003[0].severity == Severity.WASM

    def test_emscripten_excluded_dep_not_flagged(self, monkeypatch, tmp_path):
        """PEP 508 markers excluding Emscripten skip MW003 checks for that dep."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        monkeypatch.setattr(mod, "_resolve_dep_tree", lambda deps: deps)
        mod._has_wasm_compatible_wheel.cache_clear()

        notebook, contents = self._write_and_parse(
            tmp_path,
            ["jaxlib; sys_platform != 'emscripten'"],
        )
        with (
            patch(
                "marimo._pyodide.pyodide_constraints.requests.get",
                return_value=_fake_lockfile_response({}),
            ),
            patch(
                "marimo._lint.rules.wasm.incompatible_packages."
                "urllib.request.urlopen",
                side_effect=AssertionError(
                    "PyPI must not be queried for Emscripten-excluded deps"
                ),
            ),
        ):
            diagnostics = lint_notebook(
                notebook, contents, lint_config={"select": ["MW003"]}
            )
        assert not any(d.code == "MW003" for d in diagnostics)

    def test_pyemscripten_wheel_tag_compatible(self) -> None:
        """PEP 783 pyemscripten_*_wasm32 wheels match via the wasm32 suffix."""
        from marimo._lint.rules.wasm import incompatible_packages as mod

        mod._has_wasm_compatible_wheel.cache_clear()
        pypi_payload = {
            "urls": [
                {
                    "filename": (
                        "mypkg-1.0-cp312-cp312-pyemscripten_2026_0_wasm32.whl"
                    )
                }
            ]
        }
        with patch(
            "marimo._lint.rules.wasm.incompatible_packages."
            "urllib.request.urlopen",
            return_value=_FakePypiResponse(pypi_payload),
        ):
            assert mod._has_wasm_compatible_wheel("mypkg") is True
