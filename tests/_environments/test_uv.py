# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
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


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_stream_survives_a_bufferless_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Kernels replace sys.stderr with a redirect whose `buffer` can be
    None; streaming must keep reaching the callback regardless."""

    class Redirect:
        buffer = None

        def __init__(self) -> None:
            self.text: list[str] = []

        def write(self, data: str) -> int:
            self.text.append(data)
            return len(data)

    from marimo._environments.uv import uv_stream

    redirect = Redirect()
    monkeypatch.setattr(sys, "stderr", redirect)
    script = tmp_path / "nb.py"
    script.write_text(
        "# /// script\n"
        '# dependencies = ["definitely-not-a-real-pkg-xyz==99.99"]\n'
        "# ///\n",
        encoding="utf-8",
    )
    lines: list[str] = []

    with pytest.raises(UvResolutionError):
        uv_stream(["lock", "--offline", "--script", str(script)], lines.append)

    assert lines, "expected streamed diagnostics"
    assert any("No solution found" in line for line in lines), lines


def test_script_edits_ignore_an_active_virtualenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An enclosing VIRTUAL_ENV must not redirect script edits or leak
    mismatch warnings into their streamed output."""
    from unittest.mock import patch as mock_patch

    from marimo._environments import script_metadata

    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "unrelated-venv"))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/elsewhere")
    script = tmp_path / "nb.py"
    script.write_text(
        '# /// script\n# dependencies = ["numpy"]\n# ///\n',
        encoding="utf-8",
    )

    with mock_patch.object(script_metadata, "uv") as mock_uv:
        script_metadata.remove_dependencies(str(script), ["numpy"])
    env = mock_uv.call_args.kwargs["env"]
    assert "VIRTUAL_ENV" not in env
    assert "UV_PROJECT_ENVIRONMENT" not in env

    with mock_patch.object(script_metadata, "uv_stream") as mock_stream:
        script_metadata.add_dependencies(
            str(script), ["numpy"], on_output=lambda _line: None
        )
    env = mock_stream.call_args.kwargs["env"]
    assert "VIRTUAL_ENV" not in env
    assert "UV_PROJECT_ENVIRONMENT" not in env


@pytest.mark.skipif(not HAS_UV, reason="uv required")
def test_stream_callback_runs_in_the_calling_thread(tmp_path: Path) -> None:
    """Kernel callbacks resolve their notification stream through
    thread-local state; the callback must run where the caller runs."""
    import threading

    from marimo._environments.uv import uv_stream

    local = threading.local()
    local.stream = "kernel"
    seen: list[str | None] = []

    def on_output(_line: str) -> None:
        seen.append(getattr(local, "stream", None))

    script = tmp_path / "nb.py"
    script.write_text(
        "# /// script\n"
        '# dependencies = ["definitely-not-a-real-pkg-xyz==99.99"]\n'
        "# ///\n",
        encoding="utf-8",
    )
    with pytest.raises(UvResolutionError):
        uv_stream(["lock", "--offline", "--script", str(script)], on_output)

    assert seen, "expected streamed lines"
    assert all(value == "kernel" for value in seen), seen
