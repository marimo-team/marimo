# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys


def test_export_modules_import_without_click_or_starlette() -> None:
    script = """
import importlib
import pkgutil
import sys


class BlockedDependency:
    def find_spec(self, fullname, path=None, target=None):
        del path, target
        if fullname.partition(".")[0] in {"click", "starlette"}:
            raise RuntimeError(f"blocked import: {fullname}")
        return None


sys.meta_path.insert(0, BlockedDependency())
import marimo._export as export_package

for module in pkgutil.walk_packages(
    export_package.__path__, f"{export_package.__name__}."
):
    importlib.import_module(module.name)
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
