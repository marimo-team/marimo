from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="This test is flaky on Windows",
)
def test_session_schema_up_to_date() -> None:
    current_session_schema = yaml.safe_load(
        Path("marimo/_schemas/generated/session.yaml").read_text()
    )
    current_notebook_schema = yaml.safe_load(
        Path("marimo/_schemas/generated/notebook.yaml").read_text()
    )

    import sys

    sys.path.append(str(Path(__file__).parent.parent.parent))
    from scripts.generate_schemas import generate_schema

    generated_session_schema = yaml.safe_load(generate_schema("session"))
    generated_notebook_schema = yaml.safe_load(generate_schema("notebook"))
    cmd = "python scripts/generate_schemas.py"

    assert current_session_schema == generated_session_schema, (
        f"session.yaml is not up to date. Run '{cmd}' and press 'Write schema' to update."
    )
    assert current_notebook_schema == generated_notebook_schema, (
        f"notebook.yaml is not up to date. Run '{cmd}' and press 'Write schema' to update."
    )
