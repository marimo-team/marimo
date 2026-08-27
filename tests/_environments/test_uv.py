# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._environments.uv import (
    UvCommandError,
    UvMissingScriptMetadataError,
    UvNotFoundError,
    UvResolutionError,
    find_uv_bin,
    is_uv_available,
    require_uv_bin,
    uv,
)

if TYPE_CHECKING:
    from pathlib import Path

HAS_UV = is_uv_available()


def test_find_uv_bin_respects_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UV", "/opt/somewhere/uv")
    assert find_uv_bin() == "/opt/somewhere/uv"
    monkeypatch.delenv("UV")
    assert find_uv_bin() == "uv"


def test_require_uv_bin_trusts_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An explicit UV env var is trusted without a PATH lookup: uv sets it
    # when it spawns marimo, and it may point outside the PATH.
    monkeypatch.setenv("UV", "/explicit/path/to/uv")
    assert is_uv_available()
    assert require_uv_bin() == "/explicit/path/to/uv"


def test_require_uv_bin_raises_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.setenv("PATH", "")
    assert not is_uv_available()
    with pytest.raises(UvNotFoundError):
        require_uv_bin()


def test_uv_raises_not_found_for_missing_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UV", str(tmp_path / "uv-does-not-exist"))
    with pytest.raises(UvNotFoundError):
        uv(["--version"])


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_uv_captures_stdout() -> None:
    result = uv(["--version"])
    assert result.returncode == 0
    assert result.stdout.startswith("uv ")


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_nonzero_exit_raises_with_stderr() -> None:
    with pytest.raises(UvCommandError) as excinfo:
        uv(["definitely-not-a-subcommand"])
    error = excinfo.value
    assert error.stderr
    # The stringified error carries the command for logs.
    assert "definitely-not-a-subcommand" in str(error)


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_missing_script_metadata_is_refined(tmp_path: Path) -> None:
    script = tmp_path / "plain.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    with pytest.raises(UvMissingScriptMetadataError):
        uv(["export", "--script", str(script)])


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_resolution_failure_is_refined(tmp_path: Path) -> None:
    script = tmp_path / "unsatisfiable.py"
    script.write_text(
        "# /// script\n"
        '# requires-python = ">=3.11"\n'
        '# dependencies = ["definitely-not-a-real-pkg-xyz==99.99"]\n'
        "# ///\n",
        encoding="utf-8",
    )
    # --offline keeps the test hermetic; the resolver still reports
    # "No solution found when resolving dependencies".
    with pytest.raises(UvResolutionError):
        uv(["lock", "--offline", "--script", str(script)])
