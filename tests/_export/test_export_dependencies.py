# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys


def test_export_modules_do_not_require_click_or_starlette() -> None:
    script = """
import importlib
import pkgutil
import sys
from dataclasses import replace


class BlockedDependency:
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if (
            fullname.partition(".")[0] in {"click", "starlette"}
            or fullname == "marimo._cli.export"
            or fullname.startswith("marimo._cli.export.")
            or fullname == "marimo._server.api"
            or fullname.startswith("marimo._server.api.")
        ):
            raise RuntimeError(f"blocked import: {fullname}")
        return None


sys.meta_path.insert(0, BlockedDependency())
import marimo._export as export_package

for module in pkgutil.walk_packages(
    export_package.__path__, f"{export_package.__name__}."
):
    importlib.import_module(module.name)

from marimo._convert.converters import MarimoConvert
from marimo._convert.script import UnsupportedAsyncCodeError
from marimo._export.exporter import export_script
from marimo._export.requests import ScriptExportRequest

source = '''
import marimo

__generated_with = "0.0.0"
app = marimo.App()

@app.cell
async def _():
    await foo()
    return

if __name__ == "__main__":
    app.run()
'''
notebook = replace(
    MarimoConvert.from_py(source).to_ir(),
    filename="notebook.py",
)
try:
    export_script(ScriptExportRequest(notebook=notebook))
except UnsupportedAsyncCodeError:
    pass
else:
    raise AssertionError("async script export should fail")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
