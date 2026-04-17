# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

from marimo._runtime.commands import (
    ExecuteCellCommand,
)
from marimo._runtime.runtime import Kernel
from marimo._utils import async_path
from tests._messaging.mocks import MockStderr, MockStream

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import MockedKernel


class TestScriptTrace:
    @staticmethod
    def test_function_script_trace() -> None:
        p = subprocess.run(
            [sys.executable, "tests/_runtime/script_data/fn_exception.py"],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "ZeroDivisionError: division by zero" in result
        assert ('fn_exception.py", line 14') in result
        assert ('fn_exception.py", line 25') in result
        assert "bad_divide(0, x)" in result
        assert "y / x" in result
        # Test col_offset
        # Expected output:
        #    y = y / x
        #        ~~^~~
        # exact line numbers differ by python version
        if sys.version_info >= (3, 11):
            assert (
                result.split("y / x")[1]
                .split("\n")[1]
                .startswith("           ~~^~~")
            )

    @staticmethod
    def test_script_trace() -> None:
        p = subprocess.run(
            [sys.executable, "tests/_runtime/script_data/script_exception.py"],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "NameError: name 'y' is not defined" in result
        assert 'script_exception.py", line 10' in result
        assert "y = y / x" in result
        # Test col_offset
        # Expected output:
        #    y = y / x
        #        ^
        # exact line numbers differ by python version
        if sys.version_info == (3, 11):
            assert (
                result.split("y / x")[1].split("\n")[1].startswith("        ^")
            )

    @staticmethod
    def test_script_trace_with_output() -> None:
        p = subprocess.run(
            [
                sys.executable,
                "tests/_runtime/script_data/script_exception_with_output.py",
            ],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "ZeroDivisionError: division by zero" in result
        assert ('script_exception_with_output.py", line 17') in result
        assert "y / x" in result

    @staticmethod
    def test_script_trace_with_imported_file() -> None:
        p = subprocess.run(
            [
                sys.executable,
                "tests/_runtime/script_data/script_exception_with_imported_function.py",
            ],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "ZeroDivisionError: division by zero" in result

        # windows compatibility
        file_path = os.path.normpath("tests/_runtime/script_data/func.py")
        assert f'{file_path}", line 3' in result

        assert (
            os.path.normpath(
                "tests/_runtime/script_data/script_exception_with_imported_function.py"
            )
            + '", line 11'
            in result
        )
        assert "y = y / x" in result

    @staticmethod
    def test_script_trace_function() -> None:
        p = subprocess.run(
            [
                sys.executable,
                "tests/_runtime/script_data/script_exception_function.py",
            ],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "ZeroDivisionError: division by zero" in result
        assert ('script_exception_function.py", line 9') in result
        assert "y / 0" in result

    @staticmethod
    def test_script_trace_setup_cell() -> None:
        p = subprocess.run(
            [
                sys.executable,
                "tests/_runtime/script_data/script_exception_setup_cell.py",
            ],
            capture_output=True,
        )
        assert p.returncode == 1

        result = p.stderr.decode()
        assert "ZeroDivisionError" in result
        assert ('script_exception_setup_cell.py", line 10') in result
        assert "y / x" in result


class TestAppTrace:
    @staticmethod
    async def test_app_trace_body_line_number(
        execution_kernel: Kernel,
    ) -> None:
        k = execution_kernel
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                        x = 0 #L2
                        y = 0 #L3
                        y = y / x #L4
                        # filler line L5
                        # filler line L6
                        None #L7 for output expression
                    """
                    ),
                )
            ]
        )

        # Naively strip tags to check trace
        stderr_messages = MockStderr(k.stderr)
        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
        result = stderr_messages.messages[-1]
        result = tag_re.sub("", result)

        assert "ZeroDivisionError: division by zero" in result
        assert "y / x" in result
        assert "__marimo__cell_0_.py" in result
        # Test col_offset
        # Expected output:
        # File &quot;/tmp/marimo_0000000/__marimo__cell_0_.py&quot;, line 4 ...
        #   y = y / x #L4
        #       ~~^~~
        # ZeroDivisionError: division by zero
        post_file = result.split("marimo__cell")[1].split("\n")
        assert "line 4" in post_file[0]
        assert post_file[1].startswith("    y = y / x #L4")
        if sys.version_info >= (3, 11):
            assert post_file[2].startswith("        ~~^~~")

    @staticmethod
    async def test_app_trace_output_line_number(
        execution_kernel: Kernel,
    ) -> None:
        k = execution_kernel
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                        def foo(): #L2
                            x = 0 #L3
                            y = 0 #L4
                            y = y / x #L5
                            # filler line L5
                            # filler line L6
                            None #L7 for output expression
                    """
                    ),
                ),
                ExecuteCellCommand(
                    cell_id="1",
                    code="foo()",
                ),
            ]
        )

        # Naively strip tags to check trace
        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
        result = k.stderr.messages[-1]
        result = tag_re.sub("", result)

        # Test col_offset
        # Expected output:
        #  File .../__marimo__cell_1_.py&quot;, line 1, in ...
        #    foo()
        #  File .../__marimo__cell_0_.py&quot;, line 4, in foo
        #    y = y / x #L5
        #        ~~^~~
        # ZeroDivisionError: division by zero
        post_file_call = result.split("marimo__cell_1")[1].split("\n")
        assert "line 1" in post_file_call[0]
        assert "foo()" in post_file_call[1]
        post_file_error = result.split("marimo__cell_0")[1].split("\n")
        assert post_file_error[1].startswith("    y = y / x #L5")
        if sys.version_info >= (3, 11):
            assert post_file_error[2].startswith("        ~~^~~")

    @staticmethod
    async def test_app_trace_name_error_reference_caught(
        execution_kernel: Kernel,
    ) -> None:
        k = execution_kernel
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                    try:
                        R = R # Causes error since no def
                        C = 0 # Inaccessible
                    except:
                        pass
                    """
                    ),
                ),
                ExecuteCellCommand(
                    cell_id="1",
                    code=textwrap.dedent(
                        """
                    C
                    """
                    ),
                ),
            ]
        )

        # Runtime error expected- since not a kernel error check stderr

        stream_messages = MockStream(k.stream)
        stderr_messages = MockStderr(k.stderr)

        assert "C" not in k.globals
        if k.execution_type == "strict":
            assert (
                "name `R` is referenced before definition."
                in stream_messages.operations[-4]["output"]["data"][0]["msg"]
            )
            assert (
                "This cell wasn't run"
                in stream_messages.operations[-1]["output"]["data"][0]["msg"]
            )
        else:
            assert (
                "Name `C` is not defined."
                in stream_messages.operations[-2]["output"]["data"][0]["msg"]
            )
            assert "NameError" in stderr_messages.messages[0]
            assert "NameError" in stderr_messages.messages[-1]


class TestRunModeTrace:
    @staticmethod
    async def test_run_mode_trace_references_real_file(
        run_mode_kernel: MockedKernel,
        tmp_path: Path,
    ) -> None:
        """In run mode, tracebacks should reference the real notebook file."""
        # Create a real notebook file so solve_source_position can match
        notebook_code = textwrap.dedent("""\
            import marimo

            __generated_with = "0.0.0"
            app = marimo.App()


            @app.cell
            def _():
                x = 1
                return (x,)


            @app.cell
            def _(x):
                y = x + 1
                raise ValueError("boom")
                return (y,)


            if __name__ == "__main__":
                app.run()
        """)
        notebook_file = tmp_path / "test_notebook.py"
        notebook_file.write_text(notebook_code)

        k = run_mode_kernel.k
        k.app_metadata.filename = str(notebook_file)

        k.user_config = copy.deepcopy(k.user_config)
        k.user_config["runtime"]["show_tracebacks"] = True

        cell_code = textwrap.dedent(
            """
            x = 1
        """
        )
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code=cell_code),
                ExecuteCellCommand(
                    cell_id="1",
                    code=textwrap.dedent(
                        """
                        y = x + 1
                        raise ValueError("boom")
                    """
                    ),
                ),
            ]
        )

        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")

        # Collect all output: stderr messages and stream operations
        all_output = "\n".join(k.stderr.messages)
        stream_messages = MockStream(k.stream)
        for op in stream_messages.operations:
            all_output += "\n" + str(op)

        result = tag_re.sub("", all_output)

        assert "ValueError" in result or "boom" in result
        # Should reference the real notebook file, NOT __marimo__cell_
        assert "__marimo__cell_" not in result
        assert "test_notebook.py" in result

    @staticmethod
    async def test_run_mode_watch_invalidates_cache(
        run_mode_kernel: MockedKernel,
        tmp_path: Path,
    ) -> None:
        """Source position cache is invalidated on recompilation (--watch)."""
        from marimo._ast.compiler import _build_source_position_map

        notebook_v1 = textwrap.dedent("""\
            import marimo

            __generated_with = "0.0.0"
            app = marimo.App()


            @app.cell
            def _():
                x = 1
                return (x,)


            if __name__ == "__main__":
                app.run()
        """)
        notebook_file = tmp_path / "watch_notebook.py"
        notebook_file.write_text(notebook_v1)

        k = run_mode_kernel.k
        k.app_metadata.filename = str(notebook_file)

        # First compile — populates cache
        await k.run([ExecuteCellCommand(cell_id="0", code="x = 1")])
        cached = _build_source_position_map(str(notebook_file))
        assert len(cached) == 1

        # Simulate file change (--watch): add a second cell
        notebook_v2 = textwrap.dedent("""\
            import marimo

            __generated_with = "0.0.0"
            app = marimo.App()


            @app.cell
            def _():
                x = 1
                return (x,)


            @app.cell
            def _(x):
                y = x + 2
                return (y,)


            if __name__ == "__main__":
                app.run()
        """)
        notebook_file.write_text(notebook_v2)

        # Second compile — mutate_graph should clear cache
        await k.run(
            [
                ExecuteCellCommand(cell_id="0", code="x = 1"),
                ExecuteCellCommand(cell_id="1", code="y = x + 2"),
            ]
        )
        refreshed = _build_source_position_map(str(notebook_file))
        assert len(refreshed) == 2


class TestEmbedTrace:
    @staticmethod
    async def test_embed_trace(
        k: Kernel,
    ) -> None:
        await k.run(
            [
                ExecuteCellCommand(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                        from tests._runtime.script_data import (
                            script_exception_with_output
                        )
                    """
                    ),
                ),
                ExecuteCellCommand(
                    cell_id="1",
                    code=textwrap.dedent(
                        """
                        await script_exception_with_output.app.embed()
                    """
                    ),
                ),
            ]
        )

        # Naively strip tags to check trace
        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
        result = k.stderr.messages[-1]
        result = tag_re.sub("", result)

        # windows support
        file_path = await async_path.normpath(
            "tests/_runtime/script_data/script_exception_with_output.py"
        )

        assert "ZeroDivisionError: division by zero" in result
        assert (file_path + "&quot;, line 17") in result
        assert "y / x" in result
