# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._environments import environment
from marimo._environments.environment import (
    Environment,
    UvUnsupportedVersionError,
    ensure_supported_uv,
    launch,
    sync,
)
from marimo._environments.uv import (
    UvError,
    UvMissingScriptMetadataError,
    UvResolutionError,
    is_uv_available,
)

if TYPE_CHECKING:
    from pathlib import Path


def _supports_sync() -> bool:
    if not is_uv_available():
        return False
    try:
        ensure_supported_uv()
    except UvError:
        return False
    return True


SUPPORTS_SYNC = _supports_sync()

REQUIRES_PYTHON = f">={sys.version_info[0]}.{sys.version_info[1]}"

EMPTY_SCRIPT = f"""\
# /// script
# requires-python = "{REQUIRES_PYTHON}"
# dependencies = []
# ///
"""


def test_requires_restart() -> None:
    first = Environment(
        python="/env/bin/python", root="/env", action="created"
    )
    unchanged = Environment(
        python="/env/bin/python", root="/env", action="unchanged"
    )
    updated = Environment(
        python="/env/bin/python", root="/env", action="updated"
    )
    replaced = Environment(
        python="/env/bin/python", root="/env", action="replaced"
    )
    moved = Environment(
        python="/other/bin/python", root="/other", action="unchanged"
    )

    assert not first.requires_restart(None)
    assert not unchanged.requires_restart(first)
    assert not updated.requires_restart(first)
    assert replaced.requires_restart(first)
    assert moved.requires_restart(first)


def test_process_env_targets_the_environment() -> None:
    env = Environment(python="/env/bin/python", root="/env", action="created")
    base = {"UV_PROJECT_ENVIRONMENT": "/project", "PATH": "/usr/bin"}

    child = env.process_env(base)

    assert child["VIRTUAL_ENV"] == "/env"
    assert "UV_PROJECT_ENVIRONMENT" not in child
    # The environment's tools resolve first, as under `uv run`.
    bin_dir = os.path.join("/env", "Scripts" if os.name == "nt" else "bin")
    assert child["PATH"] == f"{bin_dir}{os.pathsep}/usr/bin"
    # The base mapping is not mutated.
    assert base["UV_PROJECT_ENVIRONMENT"] == "/project"


@pytest.mark.skipif(
    sys.platform == "win32", reason="shell stub is not executable on Windows"
)
def test_old_uv_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stub = tmp_path / "uv"
    stub.write_text('#!/bin/sh\necho "uv 0.5.0 (stub)"\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("UV", str(stub))

    with pytest.raises(UvUnsupportedVersionError, match="0.5.0"):
        sync(str(tmp_path / "nb.py"))


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_sync_creates_and_reuses_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # An isolated cache keeps test environments out of the user's real
    # uv cache; tmp_path is unique per run, so they would accumulate.
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    script = tmp_path / "nb.py"
    script.write_text(EMPTY_SCRIPT, encoding="utf-8")

    first = sync(str(script), cwd=str(tmp_path))
    assert first.action == "created"
    assert os.path.exists(first.python)
    assert first.python.startswith(first.root)

    again = sync(str(script), cwd=str(tmp_path))
    assert again.action == "unchanged"
    assert again.python == first.python
    assert not again.requires_restart(first)


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_sync_requires_script_metadata(tmp_path: Path) -> None:
    script = tmp_path / "plain.py"
    script.write_text("print('hi')\n", encoding="utf-8")
    with pytest.raises(UvMissingScriptMetadataError):
        sync(str(script))


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_resolution_failure_carries_the_solver_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    script = tmp_path / "nb.py"
    script.write_text(
        "# /// script\n"
        f'# requires-python = "{REQUIRES_PYTHON}"\n'
        '# dependencies = ["definitely-not-a-real-pkg-xyz==99.99"]\n'
        "# ///\n",
        encoding="utf-8",
    )
    with pytest.raises(UvResolutionError) as excinfo:
        sync(str(script), cwd=str(tmp_path))
    assert "definitely-not-a-real-pkg-xyz" in excinfo.value.stderr


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
@pytest.mark.slow
@pytest.mark.network
def test_sync_honors_index_semantics(tmp_path: Path) -> None:
    """Repro from marimo-team/marimo#10547 (requires network access).

    pip-install-test==0.0.3 exists on test.pypi.org but not on pypi.org.
    The metadata pins it to a named explicit index; delegating to
    `uv sync --script` honors the pin, where flattening the indexes into
    command-line flags could not.
    """
    script = tmp_path / "nb.py"
    script.write_text(
        "# /// script\n"
        f'# requires-python = ">={sys.version_info[0]}.{sys.version_info[1]}"\n'
        "# dependencies = [\n"
        '#     "pip-install-test==0.0.3",\n'
        "# ]\n"
        "#\n"
        "# [tool.uv.sources]\n"
        '# pip-install-test = { index = "testpypi" }\n'
        "#\n"
        "# [[tool.uv.index]]\n"
        '# url = "https://pypi.org/simple/"\n'
        "# default = true\n"
        "#\n"
        "# [[tool.uv.index]]\n"
        '# name = "testpypi"\n'
        '# url = "https://test.pypi.org/simple/"\n'
        "# explicit = true\n"
        "# ///\n",
        encoding="utf-8",
    )

    result = sync(str(script), cwd=str(tmp_path))

    site_packages = _site_packages(result.root)
    assert any(
        entry.startswith("pip_install_test") for entry in site_packages
    ), site_packages


def _site_packages(root: str) -> list[str]:
    for dirpath, dirnames, _ in os.walk(root):
        if os.path.basename(dirpath) == "site-packages":
            del dirnames[:]
            return os.listdir(dirpath)
    return []


def test_unreadable_report_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment, "ensure_supported_uv", lambda: None)

    class Completed:
        stdout = "not json"

    monkeypatch.setattr(
        environment, "uv", lambda *_args, **_kwargs: Completed()
    )
    with pytest.raises(environment.UvSyncReportError):
        sync("nb.py")


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_sync_accepts_a_python_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    script = tmp_path / "nb.py"
    script.write_text(EMPTY_SCRIPT, encoding="utf-8")
    override = f"{sys.version_info[0]}.{sys.version_info[1]}"

    env = sync(str(script), cwd=str(tmp_path), python_override=override)

    reported = subprocess.run(
        [env.python, "-c", "import sys; print(sys.version_info[:2])"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert reported == str(tuple(sys.version_info[:2]))


@pytest.mark.parametrize(
    ("raw_action", "action"),
    [
        ("create", "created"),
        ("update", "updated"),
        ("replace", "replaced"),
        ("check", "unchanged"),
        ("something-new", "updated"),
    ],
)
def test_report_actions_map_to_the_handle(
    monkeypatch: pytest.MonkeyPatch, raw_action: str, action: str
) -> None:
    report = {
        "sync": {
            "environment": {
                "path": "/env",
                "python": {"path": "/env/bin/python"},
            },
            "action": raw_action,
        }
    }

    class Completed:
        stdout = json.dumps(report)

    monkeypatch.setattr(environment, "ensure_supported_uv", lambda: None)
    monkeypatch.setattr(
        environment, "uv", lambda *_args, **_kwargs: Completed()
    )

    assert sync("nb.py").action == action


def test_launch_without_overlay_is_direct() -> None:
    env = Environment(python="/env/bin/python", root="/env", action="created")

    plan = launch(env, ["-m", "marimo"], base_env={"PATH": "/usr/bin"})

    assert plan.argv == ("/env/bin/python", "-m", "marimo")
    assert plan.env["VIRTUAL_ENV"] == "/env"
    assert not plan.start_new_session


def test_launcher_plans_start_a_new_session() -> None:
    env = Environment(python="/env/bin/python", root="/env", action="created")

    overlay = launch(env, ["-m", "marimo"], overlay=["marimo"])
    isolated = environment.launch_isolated(
        ["-m", "marimo"], overlay=["marimo"], python="3.13"
    )

    assert overlay.start_new_session
    assert isolated.start_new_session


@pytest.mark.network
@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_launch_overlay_chains_without_mutating(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Overlay packages import alongside manifest packages, and neither
    the script environment nor the manifest records them."""
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    pkg = tmp_path / "localpkg"
    (pkg / "localpkg").mkdir(parents=True)
    (pkg / "localpkg" / "__init__.py").write_text("value = 1\n")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "localpkg"\nversion = "0.1.0"\n'
    )
    script = tmp_path / "nb.py"
    script.write_text(
        "# /// script\n"
        f'# requires-python = "{REQUIRES_PYTHON}"\n'
        '# dependencies = ["six"]\n'
        "# ///\n",
        encoding="utf-8",
    )

    env = sync(str(script), cwd=str(tmp_path))
    plan = launch(
        env,
        ["-c", "import six, idna, localpkg; print('chained')"],
        overlay=["idna", f"-e {pkg}"],
    )

    result = subprocess.run(
        list(plan.argv), env=plan.env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "chained" in result.stdout
    # The script environment itself has only the manifest's packages.
    entries = _site_packages(env.root)
    assert any(entry.startswith("six") for entry in entries)
    assert not any(entry.startswith("idna") for entry in entries)
    assert "idna" not in script.read_text()


@pytest.mark.skipif(not SUPPORTS_SYNC, reason="uv >= 0.7.21 required")
def test_sync_streams_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With a callback, uv's progress streams line by line while the
    JSON report stays parseable."""
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    script = tmp_path / "nb.py"
    script.write_text(EMPTY_SCRIPT, encoding="utf-8")
    lines: list[str] = []

    env = sync(str(script), cwd=str(tmp_path), on_output=lines.append)

    assert env.action == "created"
    # Content wording is uv's, not ours; presence is the contract.
    assert lines, "expected streamed diagnostics"
