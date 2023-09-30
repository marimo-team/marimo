# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.conftest import ExecReqProvider
from marimo._runtime.runtime import Kernel


def test_capture_stdout(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.capture_stdout() as buffer:
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert k.globals["buffer"].getvalue() == "hello"


def test_capture_stderr(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.capture_stderr() as buffer:
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert k.globals["buffer"].getvalue() == "bye"
