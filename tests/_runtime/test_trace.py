# Copyright 2024 Marimo. All rights reserved.
import os
import re
import subprocess
import sys
import textwrap

from marimo._runtime.requests import (
    ExecutionRequest,
)
from marimo._runtime.runtime import Kernel


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
        assert ('fn_exception.py", line 26') in result
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
        if sys.version_info >= (3, 11):
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
        assert ('script_exception_with_output.py", line 11') in result
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
                "tests/_runtime/script_data/script_exception_with_imported_function.py"  # noqa: E501
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
        assert "The setup cell was unable to execute" in result
        assert "ZeroDivisionError: division by zero" in result
        # TODO(dmadisetti): re-enable assertion, behavior should go back to
        # expected with #4400
        # assert ('script_exception_setup_cell.py", line 10') in result
        assert "y / x" in result


class TestAppTrace:
    @staticmethod
    async def test_app_trace_body_line_number(
        execution_kernel: Kernel,
    ) -> None:
        k = execution_kernel
        await k.run(
            [
                ExecutionRequest(
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
        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
        result = k.stderr.messages[-1]
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
                ExecutionRequest(
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
                ExecutionRequest(
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
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                    try:
                        R = R # Causes error since no def
                        C = 0 # Unaccessible
                    except:
                        pass
                    """
                    ),
                ),
                ExecutionRequest(
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
        assert "C" not in k.globals
        if k.execution_type == "strict":
            assert (
                "name `R` is referenced before definition."
                in k.stream.messages[-4][1]["output"]["data"][0]["msg"]
            )
            assert (
                "This cell wasn't run"
                in k.stream.messages[-1][1]["output"]["data"][0]["msg"]
            )
        else:
            assert (
                "marimo came across the undefined variable `C` during runtime."
                in k.stream.messages[-2][1]["output"]["data"][0]["msg"]
            )
            assert "NameError" in k.stderr.messages[0]
            assert "NameError" in k.stderr.messages[-1]


class TestEmbedTrace:
    @staticmethod
    async def test_embed_trace(
        k: Kernel,
    ) -> None:
        await k.run(
            [
                ExecutionRequest(
                    cell_id="0",
                    code=textwrap.dedent(
                        """
                        from tests._runtime.script_data import (
                            script_exception_with_output
                        )
                        await script_exception_with_output.app.embed()
                    """
                    ),
                )
            ]
        )

        # Naively strip tags to check trace
        tag_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
        result = k.stderr.messages[-1]
        result = tag_re.sub("", result)

        # windows support
        file_path = os.path.normpath(
            "tests/_runtime/script_data/script_exception_with_output.py"
        )

        assert "ZeroDivisionError: division by zero" in result
        assert (file_path + "&quot;, line 11") in result
        assert "y / x" in result
