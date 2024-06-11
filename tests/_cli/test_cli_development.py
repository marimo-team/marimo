# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess


def test_cli_development_openapi() -> None:
    p = subprocess.run(
        ["marimo", "development", "openapi"],
        capture_output=True,
    )
    assert p.returncode == 0
    # Check a random endpoint
    assert "/api/export/html" in p.stdout.decode()
