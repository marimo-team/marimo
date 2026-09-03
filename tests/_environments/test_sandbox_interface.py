# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._environments import script_metadata
from marimo._environments.environment import Environment, ProcessPlan
from marimo._environments.overlay import RuntimeOverlay
from marimo._environments.sandbox import (
    NotebookSandbox,
    PackageState,
    ResolvedPackage,
    SandboxCommand,
    TerminalSandboxReporter,
)
from marimo._utils.uv_tree import DependencyTreeNode

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from marimo._environments.sandbox import LogCallback
    from marimo._environments.script_metadata import MaterializedScript


class FakeBackend:
    name = "uv"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sync_targets: list[str] = []
        self.add_requests: list[str] = []
        self.versions: dict[str, str] = {"obstore": "0.8.2"}

    def ensure_available(self) -> None:
        pass

    def prepare_source(self, source: str) -> None:
        del source

    def add(
        self,
        target: MaterializedScript,
        package: str,
        *,
        upgrade: bool,
        on_output: LogCallback | None,
    ) -> None:
        del upgrade, on_output
        self.add_requests.append(package)
        path = Path(target.path)
        content = path.read_text()
        project = script_metadata.loads(content)
        assert project is not None
        dependencies = list(project.get("dependencies", []))
        # A backend replaces a same-named entry when the request carries a
        # constraint, and leaves it alone when the request is a bare name.
        name = _requirement_name(package)
        is_bare = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package)
        for index, existing in enumerate(dependencies):
            if _requirement_name(str(existing)) == name:
                if not is_bare:
                    dependencies[index] = package
                break
        else:
            dependencies.append(package)
        project["dependencies"] = dependencies
        path.write_text(
            script_metadata.replace_block(
                content, script_metadata.dumps(project)
            )
        )

    def remove(
        self,
        target: MaterializedScript,
        package: str,
        *,
        on_output: LogCallback | None,
    ) -> None:
        del on_output
        path = Path(target.path)
        content = path.read_text()
        project = script_metadata.loads(content)
        assert project is not None
        project["dependencies"] = [
            dependency
            for dependency in project.get("dependencies", [])
            if dependency != package
        ]
        path.write_text(
            script_metadata.replace_block(
                content, script_metadata.dumps(project)
            )
        )

    def sync(
        self,
        target: MaterializedScript,
        *,
        python_override: str | None,
        on_output: LogCallback | None,
    ) -> Environment:
        del python_override, on_output
        self.sync_targets.append(target.path)
        return Environment(
            python=str(self.root / "bin" / "python"),
            root=str(self.root),
            action="updated",
        )

    def packages(
        self,
        target: MaterializedScript,
        environment: Environment | None,
    ) -> PackageState:
        del target, environment
        return PackageState(
            packages=tuple(
                ResolvedPackage(name=name, version=version)
                for name, version in self.versions.items()
            ),
            tree=DependencyTreeNode(
                name="<root>", version=None, tags=[], dependencies=[]
            ),
        )

    def launch(
        self,
        environment: Environment,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        base_env: Mapping[str, str] | None,
    ) -> ProcessPlan:
        del overlay, base_env
        return ProcessPlan(argv=(environment.python, *args), env={})


def _requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    return match.group(0).lower() if match else requirement.lower()


def test_add_edits_manifest_syncs_and_cleans_carrier(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        "---\npyproject: |\n  dependencies = []\n---\n\n# Hello\n"
    )
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore")

    assert sandbox.environment is not None
    assert "obstore==0.8.2" in notebook.read_text()
    assert len(adapter.sync_targets) == 1
    assert not list(tmp_path.glob(".marimo-*.py"))


def test_add_pins_a_bare_requirement_to_the_resolved_version(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore")

    assert adapter.add_requests == ["obstore", "obstore==0.8.2"]
    assert '"obstore==0.8.2"' in notebook.read_text()
    # The pin records the synchronized environment; it does not resync.
    assert len(adapter.sync_targets) == 1


@pytest.mark.parametrize(
    "dependency",
    ["obstore[async]", "obstore[async]>=0.7.0", "obstore[async]==0.7.0"],
)
def test_add_keeps_declared_extras(tmp_path: Path, dependency: str) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        f'# /// script\n# dependencies = ["{dependency}"]\n# ///\n'
    )
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore")

    assert adapter.add_requests == ["obstore", "obstore[async]==0.8.2"]
    assert '"obstore[async]==0.8.2"' in notebook.read_text()


def test_terminal_reporter_redacts_url_credentials() -> None:
    command = SandboxCommand(
        backend="uv",
        operation="add",
        argv=(
            "uv",
            "add",
            "pkg @ https://user:secret@example.com/pkg.whl",
        ),
    )

    with patch("marimo._cli.print.echo") as echo:
        TerminalSandboxReporter().report(command)

    rendered = echo.call_args.args[0]
    assert "user:secret" not in rendered
    assert "https://***@example.com/pkg.whl" in rendered


@pytest.mark.parametrize(
    "requirement",
    [
        "obstore>=0.8",
        "obstore==0.7.0",
        "obstore @ https://example.com/obstore-0.8.2.whl",
        "git+https://github.com/developmentseed/obstore",
    ],
)
def test_add_writes_a_constrained_requirement_as_given(
    tmp_path: Path, requirement: str
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add(requirement)

    assert adapter.add_requests == [requirement]
    assert requirement in notebook.read_text()


def test_add_never_pins_the_runtime_dependency(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    adapter.versions["marimo"] = "0.24.0"
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("marimo")

    assert adapter.add_requests == ["marimo"]
    assert '"marimo"' in notebook.read_text()


def test_add_leaves_an_unresolved_requirement_open(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("windows-curses")

    assert adapter.add_requests == ["windows-curses"]
    assert '"windows-curses"' in notebook.read_text()


def test_upgrade_reopens_an_exact_pin(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        '# /// script\n# dependencies = ["obstore==0.7.0"]\n# ///\n'
    )
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore", upgrade=True)

    assert adapter.add_requests == ["obstore>=0.7.0", "obstore==0.8.2"]
    assert '"obstore==0.8.2"' in notebook.read_text()


def test_upgrade_floors_an_unpinned_requirement_at_the_environment(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text('# /// script\n# dependencies = ["obstore"]\n# ///\n')
    adapter = FakeBackend(tmp_path / "environment")
    adapter.versions["obstore"] = "0.7.0+cpu"
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore", upgrade=True)

    # The floor drops the local segment, which PEP 440 forbids in
    # ordered comparisons; the pin keeps it.
    assert adapter.add_requests == ["obstore>=0.7.0", "obstore==0.7.0+cpu"]


def test_upgrade_pin_keeps_declared_extras(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text(
        '# /// script\n# dependencies = ["obstore[async]==0.7.0"]\n# ///\n'
    )
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.add("obstore", upgrade=True)

    assert adapter.add_requests == [
        "obstore[async]>=0.7.0",
        "obstore[async]==0.8.2",
    ]
    assert '"obstore[async]==0.8.2"' in notebook.read_text()


def test_remove_edits_markdown_manifest_and_syncs(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.md"
    notebook.write_text(
        '---\npyproject: |\n  dependencies = ["obstore"]\n---\n\n# Hi\n'
    )
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    sandbox.remove("obstore")

    assert "obstore" not in notebook.read_text()
    assert len(adapter.sync_targets) == 1
    assert not list(tmp_path.glob(".marimo-*.py"))


def test_rebind_changes_the_source_for_the_next_operation(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    for notebook in (first, second):
        notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(first), "uv", adapter=adapter)

    initial = sandbox.launch(
        ["-m", "example"], overlay=RuntimeOverlay(runtime="marimo")
    )

    sandbox.rebind(str(second))

    assert sandbox.source == str(second)
    assert sandbox.environment_source == str(first)
    assert sandbox.environment is not None
    assert initial.argv[0] == sandbox.environment.python
    assert adapter.sync_targets == [str(first)]

    plan = sandbox.launch(
        ["-m", "example"], overlay=RuntimeOverlay(runtime="marimo")
    )

    assert sandbox.environment_source == str(second)
    assert adapter.sync_targets == [str(first), str(second)]
    assert plan.argv[-2:] == ("-m", "example")


def test_packages_does_not_synchronize(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    state = sandbox.packages()

    assert state.packages[0].name == "obstore"
    assert adapter.sync_targets == []


def test_unnamed_manifest_persists_on_rebind_and_cleans_up(
    tmp_path: Path,
) -> None:
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(None, "uv", adapter=adapter)
    temporary_source = Path(sandbox.source)

    sandbox.add("obstore")
    saved = tmp_path / "saved.py"
    saved.write_text("import marimo\n")
    running_environment = sandbox.environment
    sandbox.rebind(str(saved))

    assert not temporary_source.exists()
    assert "obstore" in saved.read_text()
    assert sandbox.source == str(saved)
    assert sandbox.environment == running_environment
    assert sandbox.environment_source == str(temporary_source)


def test_close_cleans_unnamed_manifest() -> None:
    sandbox = NotebookSandbox(None, "uv", adapter=FakeBackend(Path("/env")))
    temporary_source = Path(sandbox.source)

    sandbox.close()

    assert not temporary_source.exists()


def test_runtime_dependency_cannot_be_removed(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text('# /// script\n# dependencies = ["marimo"]\n# ///\n')
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)

    with pytest.raises(
        script_metadata.ScriptMetadataError,
        match="managed by the sandbox runtime",
    ):
        sandbox.remove("marimo")

    assert 'dependencies = ["marimo"]' in notebook.read_text()
    assert adapter.sync_targets == []


def test_package_view_hides_runtime_dependency(tmp_path: Path) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("# /// script\n# dependencies = []\n# ///\n")
    adapter = FakeBackend(tmp_path / "environment")
    sandbox = NotebookSandbox(str(notebook), "uv", adapter=adapter)
    original_packages = adapter.packages

    def packages_with_marimo(
        target: MaterializedScript, environment: Environment | None
    ) -> PackageState:
        state = original_packages(target, environment)
        assert state.tree is not None
        state.tree.dependencies.append(
            DependencyTreeNode(
                name="marimo", version="0.24.0", tags=[], dependencies=[]
            )
        )
        return PackageState(
            packages=(
                *state.packages,
                ResolvedPackage(name="marimo", version="0.24.0"),
            ),
            tree=state.tree,
        )

    adapter.packages = packages_with_marimo  # type: ignore[method-assign]

    state = sandbox.packages()

    assert [package.name for package in state.packages] == ["obstore"]
    assert state.tree is not None
    assert [node.name for node in state.tree.dependencies] == []


def test_pixi_launch_layers_the_runtime_overlay_through_uv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._environments import pixi
    from marimo._environments.backends import PixiBackendAdapter

    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: "/stub/pixi")

    root = tmp_path / "environment"
    environment = Environment(
        python=str(root / "bin" / "python"),
        root=str(root),
        action="unchanged",
    )
    checkout = tmp_path / "marimo-checkout"

    plan = PixiBackendAdapter().launch(
        environment,
        ["-m", "marimo"],
        overlay=RuntimeOverlay(
            runtime=f"-e {checkout}", command=("nbformat",)
        ),
        base_env={"PATH": "/bin"},
    )

    pairs = list(zip(plan.argv, plan.argv[1:], strict=False))
    assert plan.argv[:5] == (
        "/stub/pixi",
        "exec",
        "--spec",
        pixi.UV_OVERLAY_SPEC,
        "uv",
    )
    assert ("--python", environment.python) in pairs
    # A local runtime becomes --with-editable; other entries --with.
    assert ("--with-editable", str(checkout)) in pairs
    assert ("--with", "nbformat") in pairs
    assert plan.argv[-3:] == ("python", "-m", "marimo")
    assert plan.env["CONDA_PREFIX"] == str(root)
    assert plan.start_new_session


def test_pixi_package_list_exposes_only_managed_pypi_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments import pixi
    from marimo._environments.backends import PixiBackendAdapter
    from marimo._environments.script_metadata import MaterializedScript

    records = [
        {
            "name": "zlib",
            "version": "1.3.1",
            "kind": "conda",
            "is_explicit": True,
            "depends": [],
        },
        {
            "name": "attrs",
            "version": "25.3.0",
            "kind": "pypi",
            "is_explicit": True,
            "depends": [],
        },
    ]
    monkeypatch.setattr(
        pixi,
        "list_script_packages",
        lambda *_args, **_kwargs: records,
    )
    target = MaterializedScript(
        path=str(tmp_path / "notebook.py"), directory=str(tmp_path)
    )

    state = PixiBackendAdapter().packages(target, environment=None)

    assert [(package.name, package.version) for package in state.packages] == [
        ("attrs", "25.3.0")
    ]
    assert state.tree is not None
    assert [node.name for node in state.tree.dependencies] == ["zlib", "attrs"]


@pytest.mark.skipif(
    sys.platform == "win32", reason="stub executable is a POSIX shell"
)
def test_pixi_launch_does_not_require_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._environments import pixi, uv

    root = tmp_path / "pixi-environment"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "python").touch()
    executable = tmp_path / "pixi"
    executable.write_text(
        "#!/bin/sh\n"
        'if [ "$2" = "--help" ]; then echo "--script"; exit 0; fi\n'
        f"echo \"The script environment has been installed at '{root}'.\" >&2\n"
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(pixi, "find_pixi_bin", lambda: str(executable))

    def fail_uv() -> str:
        raise AssertionError("pixi selected the uv executable")

    monkeypatch.setattr(uv, "require_uv_bin", fail_uv)
    notebook = tmp_path / "notebook.py"
    notebook.write_text('# /// script\n# dependencies = ["marimo"]\n# ///\n')

    sandbox = NotebookSandbox(str(notebook), "pixi")
    plan = sandbox.launch(
        ["-m", "example"], overlay=RuntimeOverlay(runtime="marimo")
    )

    # The overlay rides uv, but uv arrives through `pixi exec` -- never
    # from the PATH (fail_uv above proves it was not consulted).
    assert plan.argv[0] == str(executable)
    assert plan.argv[1:5] == ("exec", "--spec", pixi.UV_OVERLAY_SPEC, "uv")
    assert plan.env["CONDA_PREFIX"] == str(root)
    assert plan.env["CONDA_DEFAULT_ENV"] == root.name
