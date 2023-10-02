# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

from marimo._runtime.conftest import ExecReqProvider, MockedKernel


def _has_output(
    messages: list[Tuple[str, Dict[Any, Any]]], pattern: str
) -> bool:
    for op, data in messages:
        if (
            op == "cell-op"
            and data["output"] is not None
            and re.match(pattern, data["output"]["data"])
        ):
            return True
    return False


def test_capture_stdout(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
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
    assert not mocked_kernel.stdout.messages
    assert mocked_kernel.stderr.messages == ["bye"]
    assert mocked_kernel.k.globals["buffer"].getvalue() == "hello"


def test_capture_stderr(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
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
    assert mocked_kernel.stdout.messages == ["hello"]
    assert not mocked_kernel.stderr.messages
    assert mocked_kernel.k.globals["buffer"].getvalue() == "bye"


def test_capture_both(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
        [
            # in python < 3.9, parenthesizing multiple context managers is
            # not allowed, hence the line continuation
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.capture_stderr() as stderr, \
                     mo.capture_stdout() as stdout:
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert not mocked_kernel.stdout.messages
    assert not mocked_kernel.stderr.messages
    assert mocked_kernel.k.globals["stdout"].getvalue() == "hello"
    assert mocked_kernel.k.globals["stderr"].getvalue() == "bye"


def test_redirect_stdout(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.redirect_stdout():
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert not mocked_kernel.stdout.messages
    assert mocked_kernel.stderr.messages == ["bye"]
    assert _has_output(mocked_kernel.stream.messages, r".*hello.*")
    assert not _has_output(mocked_kernel.stream.messages, r".*bye.*")


def test_redirect_stderr(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.redirect_stderr():
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert mocked_kernel.stdout.messages == ["hello"]
    assert not mocked_kernel.stderr.messages

    assert _has_output(mocked_kernel.stream.messages, r".*bye.*")
    assert not _has_output(mocked_kernel.stream.messages, r".*hello.*")


def test_redirect_both(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    mocked_kernel.k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                import sys
                with mo.redirect_stdout(), mo.redirect_stderr():
                    sys.stdout.write('hello')
                    sys.stderr.write('bye')
                """
            )
        ]
    )
    assert not mocked_kernel.stdout.messages
    assert not mocked_kernel.stderr.messages

    assert _has_output(mocked_kernel.stream.messages, r".*bye.*")
    assert _has_output(mocked_kernel.stream.messages, r".*hello.*")
