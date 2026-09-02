# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._environments import pixi, script_metadata
from marimo._environments.overlay import RuntimeOverlay

if TYPE_CHECKING:
    from pathlib import Path

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="stub executables are POSIX shell"
)


def _stub_pixi(tmp_path: Path, script: str) -> str:
    path = tmp_path / "pixi"
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@posix_only
def test_sync_parses_the_install_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "envs" / "default"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "python").touch()
    # The message arrives styled; the parser must see through ANSI.
    stub = _stub_pixi(
        tmp_path,
        'printf "\\033[32m+\\033[0m The script environment has been '
        f'installed at \'%s\'.\\n" "{root}" >&2\n',
    )
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)

    notebook = tmp_path / "nb.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    handle = pixi.sync(str(notebook))
    assert handle.root == str(root)
    assert handle.python == str(root / "bin" / "python")
    assert handle.action == "updated"


@posix_only
def test_sync_surfaces_command_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_pixi(tmp_path, "echo 'no solution' >&2\nexit 7\n")
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)

    with pytest.raises(pixi.PixiCommandError) as excinfo:
        pixi.sync(str(tmp_path / "nb.py"))
    assert excinfo.value.returncode == 7
    assert "no solution" in str(excinfo.value)


@posix_only
def test_add_reports_command_separately_from_backend_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub = _stub_pixi(tmp_path, "echo 'pixi output'\n")
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)
    notebook = tmp_path / "nb.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    output: list[str] = []
    commands: list[tuple[str, ...]] = []

    pixi.add(
        str(notebook),
        "polars",
        cwd=str(tmp_path),
        on_output=output.append,
        on_command=lambda command: commands.append(tuple(command)),
    )

    assert output == ["pixi output\n"]
    assert commands == [
        (stub, "add", "--script", str(notebook), "--pypi", "polars")
    ]
    assert capsys.readouterr().err == ""


@posix_only
@pytest.mark.parametrize(
    ("package", "expected"),
    [
        # `pixi update` refreshes the solve for a package it knows by name.
        ("polars", ("update", "polars")),
        # It does not take requirements; a constrained upgrade rewrites
        # the manifest entry instead.
        ("polars>=1.2.3", ("add", "--pypi", "polars>=1.2.3")),
    ],
)
def test_upgrade_verb_depends_on_the_requirement_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package: str,
    expected: tuple[str, ...],
) -> None:
    stub = _stub_pixi(tmp_path, "exit 0\n")
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)
    notebook = tmp_path / "nb.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    commands: list[tuple[str, ...]] = []

    pixi.add(
        str(notebook),
        package,
        cwd=str(tmp_path),
        upgrade=True,
        on_command=lambda command: commands.append(tuple(command)),
    )

    verb, *arguments = expected
    assert commands == [(stub, verb, "--script", str(notebook), *arguments)]


@posix_only
def test_low_level_add_is_silent_without_a_reporter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stub = _stub_pixi(tmp_path, "exit 0\n")
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)
    notebook = tmp_path / "nb.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")

    pixi.add(str(notebook), "polars", cwd=str(tmp_path))

    assert capsys.readouterr().err == ""


def test_terminal_sandbox_reporter_uses_lifecycle_label(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from marimo._environments.sandbox import (
        SandboxCommand,
        TerminalSandboxReporter,
    )

    TerminalSandboxReporter().report(
        SandboxCommand(
            backend="pixi",
            operation="remove",
            argv=("/local/pixi", "remove", "obstore"),
        )
    )

    assert capsys.readouterr().err == (
        "Removing from sandbox: /local/pixi remove obstore\n"
    )


@posix_only
def test_pixi_adapter_reports_without_polluting_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments.backends import PixiBackendAdapter
    from marimo._environments.sandbox import SandboxCommand
    from marimo._environments.script_metadata import MaterializedScript

    class Recorder:
        def __init__(self) -> None:
            self.commands: list[SandboxCommand] = []

        def report(self, command: SandboxCommand) -> None:
            self.commands.append(command)

    stub = _stub_pixi(tmp_path, "echo 'pixi output'\n")
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)
    notebook = tmp_path / "nb.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    recorder = Recorder()
    output: list[str] = []

    PixiBackendAdapter(recorder).add(
        MaterializedScript(path=str(notebook), directory=str(tmp_path)),
        "polars",
        upgrade=False,
        on_output=output.append,
    )

    assert output == ["pixi output\n"]
    assert recorder.commands == [
        SandboxCommand(
            backend="pixi",
            operation="add",
            argv=(
                stub,
                "add",
                "--script",
                str(notebook),
                "--pypi",
                "polars",
            ),
        )
    ]


def test_launch_activates_the_conda_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments.environment import Environment
    from marimo._environments.overlay import RuntimeOverlay

    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: "/stub/pixi")
    root = str(tmp_path / "prefix")
    handle = Environment(
        python=os.path.join(root, "bin", "python"),
        root=root,
        action="updated",
    )
    plan = pixi.launch(
        handle,
        ["-m", "marimo"],
        overlay=RuntimeOverlay(runtime="marimo==1.0"),
        base_env={"PATH": "/usr/bin", "VIRTUAL_ENV": "/elsewhere"},
    )
    # The prefix is activated the way `pixi run` would, and the process
    # itself runs under uv's layer.
    assert plan.argv[-3:] == ("python", "-m", "marimo")
    assert plan.env["CONDA_PREFIX"] == root
    assert "VIRTUAL_ENV" not in plan.env
    assert plan.env["PATH"].startswith(os.path.join(root, "bin") + os.pathsep)


def test_fallback_plan_reflects_this_interpreter() -> None:
    """With no manifest there is nothing to sandbox; the plan runs this
    interpreter, and inherited activation state must describe it rather
    than an enclosing shell's."""
    from marimo._environments import backends

    plan = backends.launch_fallback(
        ["-m", "example"],
        base_env={
            "VIRTUAL_ENV": "/stale/venv",
            "UV_PROJECT_ENVIRONMENT": "/elsewhere",
            "PATH": "/usr/bin",
        },
    )

    assert plan.argv[0] == sys.executable
    assert "UV_PROJECT_ENVIRONMENT" not in plan.env
    if sys.prefix != sys.base_prefix:
        assert plan.env["VIRTUAL_ENV"] == sys.prefix
    else:
        assert "VIRTUAL_ENV" not in plan.env


def test_ensure_metadata_block_respects_shebangs(tmp_path: Path) -> None:
    plain = tmp_path / "plain.py"
    plain.write_text("print('hi')\n")
    script_metadata.ensure_metadata_block(str(plain))
    assert plain.read_text().startswith("# /// script\n")

    executable = tmp_path / "executable.py"
    executable.write_text("#!/usr/bin/env python\nprint('hi')\n")
    script_metadata.ensure_metadata_block(str(executable))
    lines = executable.read_text().splitlines()
    assert lines[0] == "#!/usr/bin/env python"
    assert lines[1] == "# /// script"

    # A script that already has a block is left alone.
    before = plain.read_text()
    script_metadata.ensure_metadata_block(str(plain))
    assert plain.read_text() == before


@posix_only
def test_ensure_marimo_adds_a_loose_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The manifest carries loose `marimo` for standalone `pixi run`;
    the launch overlay owns the version, so no pin and never a local
    path -- even from a development checkout."""
    stub = _stub_pixi(tmp_path, 'echo "$@" > "$0.args"\n')
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)

    notebook = tmp_path / "notebook.py"
    notebook.write_text('# /// script\n# dependencies = ["six"]\n# ///\n')

    pixi.ensure_marimo(str(notebook))

    recorded = (tmp_path / "pixi.args").read_text().split()
    assert recorded == [
        "add",
        "--script",
        str(notebook),
        "--pypi",
        "marimo",
    ]


@pytest.mark.network
@pytest.mark.skipif(
    not pixi.find_pixi_bin(), reason="pixi is required for this test"
)
def test_overlay_chains_the_conda_prefix(tmp_path: Path) -> None:
    """The behavior UV_OVERLAY_SPEC floors: uv's ephemeral overlay
    environment, created from the conda interpreter, chains the
    prefix's site-packages with overlay-first precedence."""
    import subprocess

    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        "# /// script\n"
        '# dependencies = ["six"]\n'
        "#\n"
        "# [tool.pixi.workspace]\n"
        '# channels = ["conda-forge"]\n'
        "# ///\n"
    )
    environment = pixi.sync(str(notebook), cwd=str(tmp_path))

    # `attrs` stands in for the runtime requirement so the layer resolves
    # cheaply; what matters is that it chains the prefix behind it.
    plan = pixi.launch(
        environment,
        [
            "-c",
            (
                "import attrs, six, sys; "
                "print('six', six.__file__); "
                "print('exe', sys.executable)"
            ),
        ],
        overlay=RuntimeOverlay(runtime="attrs"),
    )
    completed = subprocess.run(
        list(plan.argv), env=plan.env, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    # six resolves from the conda prefix, attrs from the overlay, and
    # the interpreter is uv's ephemeral chain -- not the prefix python.
    assert environment.root in completed.stdout
    assert environment.python not in completed.stdout.splitlines()[-1]


def test_command_env_drops_enclosing_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/venv")
    monkeypatch.setenv("CONDA_PREFIX", "/conda")
    monkeypatch.setenv("PIXI_PROJECT_MANIFEST", "/pixi.toml")
    env = pixi.command_env()
    assert "VIRTUAL_ENV" not in env
    assert "CONDA_PREFIX" not in env
    assert "PIXI_PROJECT_MANIFEST" not in env
