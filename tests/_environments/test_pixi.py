# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING

import pytest

from marimo._environments import pixi, script_metadata
from marimo._environments.errors import (
    EnvironmentManagerError,
    SandboxRestartRequired,
)
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
    root = tmp_path / "envs" / "Zoë's environment"
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


@pytest.mark.parametrize("active_root", [None, "/env", "/previous-env"])
def test_pixi_sync_requires_restart_when_the_live_prefix_changes(
    active_root: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments.backends import PixiBackendAdapter
    from marimo._environments.environment import Environment
    from marimo._environments.script_metadata import MaterializedScript

    synced = Environment(
        python="/env/bin/python", root="/env", action="updated"
    )
    monkeypatch.setattr(pixi, "sync", lambda *_args, **_kwargs: synced)
    active = (
        Environment(
            python=f"{active_root}/bin/python",
            root=active_root,
            action="unchanged",
        )
        if active_root is not None
        else None
    )

    def synchronize() -> Environment:
        return PixiBackendAdapter().sync(
            MaterializedScript(path="/notebook.py", directory="/"),
            python_override=None,
            on_output=None,
            active_environment=active,
        )

    if active_root == "/previous-env":
        with pytest.raises(SandboxRestartRequired, match="Restart the kernel"):
            synchronize()
    else:
        assert synchronize() == synced


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
def test_sync_refines_missing_script_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _stub_pixi(
        tmp_path,
        "echo 'The script does not contain a' >&2\n"
        "echo 'PEP 723 metadata block' >&2\n"
        "exit 1\n",
    )
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: stub)

    with pytest.raises(pixi.PixiMissingScriptMetadataError):
        pixi.sync(str(tmp_path / "nb.py"))


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


def test_pixi_adapter_uses_native_pypi_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments.backends import PixiBackendAdapter
    from marimo._environments.sandbox import PackageState, ResolvedPackage
    from marimo._environments.script_metadata import MaterializedScript
    from marimo._utils.uv_tree import DependencyTag, DependencyTreeNode

    records = [
        {
            "name": "polars",
            "version": "1.44.1",
            "kind": "pypi",
        },
        {
            "name": "polars_runtime_32",
            "version": "1.44.1",
            "kind": "pypi",
        },
        {
            "name": "python",
            "version": "3.14.7",
            "kind": "conda",
        },
        {
            "name": "libzlib",
            "version": "1.3.2",
            "kind": "conda",
        },
        {
            "name": "xarray",
            "version": "2026.7.0",
            "kind": "pypi",
        },
    ]
    monkeypatch.setattr(
        pixi, "list_script_packages", lambda *_args, **_kwargs: records
    )
    monkeypatch.setattr(
        pixi,
        "tree_script_packages",
        lambda *_args, **_kwargs: (
            "Installed for: osx-arm64\n"
            "├── polars 1.44.1\n"
            "│   └── polars_runtime_32 1.44.1\n"
            "├── xarray 2026.7.0\n"
            "│   └── polars_runtime_32 1.44.1  (*)\n"
            "└── python 3.14.7\n"
            "    └── libzlib 1.3.2\n"
        ),
    )
    target = MaterializedScript(
        path=str(tmp_path / "notebook.py"), directory=str(tmp_path)
    )

    state = PixiBackendAdapter().packages(target, environment=None)

    assert state == PackageState(
        packages=(
            ResolvedPackage(name="polars", version="1.44.1"),
            ResolvedPackage(name="polars_runtime_32", version="1.44.1"),
            ResolvedPackage(name="xarray", version="2026.7.0"),
        ),
        tree=DependencyTreeNode(
            name="<root>",
            version=None,
            tags=[],
            dependencies=[
                DependencyTreeNode(
                    name="polars",
                    version="1.44.1",
                    tags=[],
                    dependencies=[
                        DependencyTreeNode(
                            name="polars_runtime_32",
                            version="1.44.1",
                            tags=[],
                            dependencies=[],
                        )
                    ],
                ),
                DependencyTreeNode(
                    name="xarray",
                    version="2026.7.0",
                    tags=[],
                    dependencies=[
                        DependencyTreeNode(
                            name="polars_runtime_32",
                            version="1.44.1",
                            tags=[DependencyTag(kind="dedupe", value="true")],
                            dependencies=[],
                        )
                    ],
                ),
            ],
        ),
    )


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
    # The conventional prefix paths are exposed, and the process itself
    # runs under uv's layer.
    assert plan.argv[-2:] == ("-m", "marimo")
    assert plan.env["CONDA_PREFIX"] == root
    assert "VIRTUAL_ENV" not in plan.env
    expected_paths = (
        [
            root,
            os.path.join(root, "Library", "mingw-w64", "bin"),
            os.path.join(root, "Library", "usr", "bin"),
            os.path.join(root, "Library", "bin"),
            os.path.join(root, "Scripts"),
            os.path.join(root, "bin"),
        ]
        if os.name == "nt"
        else [os.path.join(root, "bin")]
    )
    assert plan.env["PATH"] == os.pathsep.join([*expected_paths, "/usr/bin"])
    assert plan.start_new_session


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
    """The manifest carries loose `marimo` for standalone
    `pixi run --script`; the launch overlay owns the version, so no pin and
    never a local path -- even from a development checkout."""
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
def test_live_pixi_mutation_after_rename_requires_restart(
    tmp_path: Path,
) -> None:
    from marimo._environments.sandbox import NotebookSandbox

    original = tmp_path / "original.py"
    renamed = tmp_path / "renamed.py"
    original.write_text(
        '# /// script\n# dependencies = ["six==1.16.0"]\n'
        '# [tool.pixi.workspace]\n# channels = ["conda-forge"]\n# ///\n'
    )
    running = pixi.sync(str(original), cwd=str(tmp_path))
    sandbox = NotebookSandbox(str(original), "pixi", environment=running)
    original.rename(renamed)
    sandbox.rebind(str(renamed))

    with pytest.raises(SandboxRestartRequired, match="Restart the kernel"):
        sandbox.add("boltons")

    assert sandbox.environment == running
    assert "boltons" in renamed.read_text()
    assert not original.exists()

    # A later rejected dependency must not poison the saved manifest or
    # prevent the user from restarting into the successful change.
    before = renamed.read_text()
    with pytest.raises(EnvironmentManagerError):
        sandbox.add("six==999999")
    assert renamed.read_text() == before
    restarted = pixi.sync(str(renamed), cwd=str(tmp_path))
    assert restarted.root != running.root


@pytest.mark.network
@pytest.mark.skipif(
    not pixi.find_pixi_bin(), reason="pixi is required for this test"
)
def test_live_pixi_upgrade_installs_the_reported_version(
    tmp_path: Path,
) -> None:
    import subprocess

    from marimo._environments.sandbox import NotebookSandbox

    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        '# /// script\n# dependencies = ["six==1.16.0"]\n'
        '# [tool.pixi.workspace]\n# channels = ["conda-forge"]\n# ///\n'
    )
    running = pixi.sync(str(notebook), cwd=str(tmp_path))
    sandbox = NotebookSandbox(str(notebook), "pixi", environment=running)
    sandbox.add("six", upgrade=True)
    reported = next(
        p.version for p in sandbox.packages().packages if p.name == "six"
    )
    installed = subprocess.check_output(
        [
            running.python,
            "-c",
            "from importlib.metadata import version; print(version('six'))",
        ],
        text=True,
    )
    assert installed.strip() == reported
    assert reported != "1.16.0"


@pytest.mark.network
@pytest.mark.skipif(
    not pixi.find_pixi_bin(), reason="pixi is required for this test"
)
@pytest.mark.parametrize("enclosing", ["plain", "uv", "conda", "pixi"])
def test_overlay_chains_the_conda_prefix(
    tmp_path: Path, enclosing: str
) -> None:
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
    base_env = os.environ.copy()
    if enclosing == "uv":
        base_env.update(
            VIRTUAL_ENV="/outer/uv", UV_PROJECT_ENVIRONMENT="/outer/project"
        )
    elif enclosing in ("conda", "pixi"):
        base_env.update(
            CONDA_PREFIX="/outer/conda",
            CONDA_PREFIX_1="/outer/base",
            CONDA_SHLVL="2",
        )
        if enclosing == "pixi":
            base_env.update(
                PIXI_PROJECT_MANIFEST="/outer/pixi.toml",
                PIXI_ENVIRONMENT_NAME="outer",
            )
    plan = pixi.launch(
        environment,
        [
            "-c",
            (
                "import attrs, six, sys, os, json; "
                "print('six', six.__file__); "
                "print('exe', sys.executable); "
                "print(json.dumps(dict(prefix=os.environ['CONDA_PREFIX'], "
                "base=sys.base_prefix, overlay=sys.prefix, "
                "venv=os.environ['VIRTUAL_ENV'], "
                "path=os.environ['PATH'].split(os.pathsep), "
                "pixi=os.environ.get('PIXI_ENVIRONMENT_NAME'))))"
            ),
        ],
        overlay=RuntimeOverlay(runtime="attrs"),
        base_env=base_env,
    )
    completed = subprocess.run(
        list(plan.argv), env=plan.env, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
    # six resolves from the conda prefix, attrs from the overlay, and
    # the interpreter is uv's ephemeral chain -- not the prefix python.
    assert environment.root in completed.stdout
    assert environment.python not in completed.stdout.splitlines()[1]
    import json

    identity = json.loads(completed.stdout.splitlines()[-1])
    assert identity["prefix"] == identity["base"] == environment.root
    assert identity["venv"] == identity["overlay"] != environment.root
    assert identity["pixi"] is None
    expected_paths = [
        os.path.dirname(completed.stdout.splitlines()[1].removeprefix("exe ")),
        *pixi._activation_path_entries(environment.root),
    ]
    assert identity["path"][: len(expected_paths)] == expected_paths


def test_command_env_drops_enclosing_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activation = {
        "VIRTUAL_ENV": "/venv",
        "UV_PROJECT_ENVIRONMENT": "/uv-project",
        "CONDA_PREFIX": "/conda",
        "CONDA_DEFAULT_ENV": "outer",
        "PIXI_PROJECT_MANIFEST": "/pixi.toml",
        "PIXI_PROJECT_ROOT": "/pixi",
        "PIXI_ENVIRONMENT_NAME": "outer",
        "PIXI_IN_SHELL": "1",
    }
    for key, value in activation.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("KEEP_ME", "preserved")
    env = pixi.command_env()
    assert not activation.keys() & env.keys()
    assert env["KEEP_ME"] == "preserved"
