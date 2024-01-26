# Copyright 2024 Marimo. All rights reserved.
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_file_path(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("x = __file__"),
        ]
    )

    assert k.globals["x"] == "/app/test.py"

    k.app_metadata.filename = "/app/test2.py"

    k.run(
        [
            exec_req.get("y = __file__"),
        ]
    )

    assert k.globals["y"] == "/app/test2.py"
