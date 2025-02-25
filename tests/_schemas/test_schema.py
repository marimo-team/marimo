from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="This test is flaky on Windows",
)
def test_session_schema_up_to_date() -> None:
    with open("marimo/_schemas/generated/session.yaml") as f:
        current_content = yaml.safe_load(f)

    script_path = (
        Path(__file__).parent.parent.parent / "scripts" / "generate_schemas.py"
    )
    result = subprocess.run([script_path], capture_output=True, text=True)
    generated_content = yaml.safe_load(result.stdout)

    cmd = "marimo edit scripts/generate_schemas.py"
    assert current_content == generated_content, (
        f"session.yaml is not up to date. Run '{cmd}' and press 'Write schema' to update."
    )
