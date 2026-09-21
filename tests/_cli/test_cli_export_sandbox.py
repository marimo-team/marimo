# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import sys
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import click
import pytest
from click.testing import CliRunner

from marimo._cli.export import session, thumbnail
from marimo._environments import backends, environment, pixi, uv
from marimo._environments.environment import Environment, ProcessPlan
from marimo._session.state.serialize import get_session_cache_file

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from marimo._environments.overlay import RuntimeOverlay
    from marimo._environments.sandbox import Backend


@pytest.fixture
def local_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    # Substitute dependency installation, but run the real export workers.
    async def sync(path: str, *, backend: Backend) -> Environment:
        source = Path(path)
        root = source.with_suffix("")
        root.mkdir(exist_ok=True)
        (root / "sandbox_dependency.py").write_text(
            f"NAME = {source.stem!r}\nBACKEND = {backend!r}\n",
            encoding="utf-8",
        )
        return Environment(sys.executable, str(root), "unchanged")

    def launch(
        env: Environment,
        args: Sequence[str],
        *,
        overlay: RuntimeOverlay,
        backend: Backend,
        base_env: Mapping[str, str] | None = None,
    ) -> ProcessPlan:
        del overlay
        process_env = dict(os.environ if base_env is None else base_env)
        process_env["TEST_EXPORT_BACKEND"] = backend
        process_env["PYTHONPATH"] = os.pathsep.join(
            [env.root, process_env.get("PYTHONPATH", "")]
        )
        return ProcessPlan((env.python, *args), process_env, True)

    monkeypatch.setattr(backends, "sync_notebook_async", sync)
    monkeypatch.setattr(environment, "launch", partial(launch, backend="uv"))
    monkeypatch.setattr(pixi, "launch", partial(launch, backend="pixi"))
    monkeypatch.setattr(backends, "ensure_available", lambda _: None)
    monkeypatch.setattr(environment, "require_uv_bin", lambda: "uv")
    monkeypatch.setattr(uv, "require_uv_bin", lambda: "uv")
    monkeypatch.setattr(pixi, "require_pixi_bin", lambda: "pixi")


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> None:
    page = AsyncMock()
    context = AsyncMock()
    context.new_page.return_value = page
    browser = AsyncMock()
    browser.new_context.return_value = context
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    manager = AsyncMock()
    manager.__aenter__.return_value = playwright
    module = ModuleType("playwright.async_api")
    module.async_playwright = lambda: manager
    module.TimeoutError = TimeoutError
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)
    monkeypatch.setattr(
        thumbnail.DependencyManager.playwright, "require", lambda _: None
    )


def write_notebook(path: Path) -> None:
    path.write_text(
        """# /// script
# dependencies = ["marimo", "sandbox-dependency"]
# ///
import marimo

app = marimo.App()

@app.cell
def _():
    import json
    import os
    from pathlib import Path
    import marimo as mo
    import sandbox_dependency

    result = Path(mo.cli_args()["output-dir"]) / (sandbox_dependency.NAME + ".json")
    result.write_text(json.dumps({"value": mo.cli_args()["value"], "pid": os.getpid(), "backend": sandbox_dependency.BACKEND, "launcher": os.environ["TEST_EXPORT_BACKEND"], "sandbox_arg": mo.cli_args().get("sandbox")}))
    return

if __name__ == "__main__":
    app.run()
""",
        encoding="utf-8",
    )


@pytest.mark.parametrize("export_format", ["session", "thumbnail"])
@pytest.mark.parametrize("directory", [False, True])
@pytest.mark.parametrize(
    ("option", "backend"),
    [("--sandbox", "uv"), ("--sandbox=uv", "uv"), ("--sandbox=pixi", "pixi")],
)
@pytest.mark.usefixtures("local_environments", "browser")
def test_sandbox_exports_execute_in_each_notebook_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    export_format: str,
    directory: bool,
    option: str,
    backend: Backend,
) -> None:
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    paths = [notebooks / "first.py", notebooks / "second.py"]
    for path in paths:
        write_notebook(path)
    sources = [path.read_text() for path in paths]
    target = notebooks if directory else paths[0]
    command = (
        session.session if export_format == "session" else thumbnail.thumbnail
    )
    args = [str(target), option]
    if export_format == "thumbnail":
        args.append("--execute")
    args.extend(
        [
            "--",
            "--value",
            "forwarded",
            "--sandbox=pixi",
            "--output-dir",
            str(tmp_path),
        ]
    )

    if backend == "pixi":

        def unavailable_uv() -> str:
            raise AssertionError("Pixi exports must not require a host uv")

        monkeypatch.setattr(uv, "require_uv_bin", unavailable_uv)
        monkeypatch.setattr(environment, "require_uv_bin", unavailable_uv)

    # Re-enter as the Playwright bootstrap would, preserving notebook args.
    def bootstrap(plan: ProcessPlan) -> int:
        assert plan.argv[0] == backend
        assert "playwright" in plan.argv
        argv = list(plan.argv[plan.argv.index("marimo") + 3 :])
        with monkeypatch.context() as child:
            for key, value in plan.env.items():
                child.setenv(key, value)
            result = CliRunner().invoke(command, argv)
        assert result.exit_code == 0, result.output
        return result.exit_code

    monkeypatch.setattr(thumbnail, "_wait_on_plan", bootstrap)
    monkeypatch.setattr(
        sys, "argv", ["marimo", "export", export_format, *args]
    )
    result = CliRunner().invoke(command, args)
    assert result.exit_code == 0, result.output

    executed = paths if directory else paths[:1]
    results = {
        path.stem: json.loads(path.read_text())
        for path in tmp_path.glob("*.json")
    }
    assert set(results) == {path.stem for path in executed}
    pids = {data["pid"] for data in results.values()}
    assert os.getpid() not in pids
    assert len(pids) == len(executed)
    assert {data["value"] for data in results.values()} == {"forwarded"}
    assert {
        (data["backend"], data["launcher"]) for data in results.values()
    } == {(backend, backend)}
    assert {data["sandbox_arg"] for data in results.values()} == {"pixi"}
    assert [path.read_text() for path in paths] == sources

    if export_format == "session":
        # Fresh snapshots skip environment preparation as well as execution.
        def unavailable(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(
                "A fresh snapshot must not provision dependencies"
            )

        monkeypatch.setattr(backends, "sync_notebook_async", unavailable)
        monkeypatch.setattr(backends, "ensure_available", unavailable)
        result = CliRunner().invoke(command, args)
        assert result.exit_code == 0, result.output
        assert "skip:" in result.output
        assert {
            path.stem: json.loads(path.read_text())
            for path in tmp_path.glob("*.json")
        } == results


@pytest.mark.parametrize("continue_on_error", [False, True])
@pytest.mark.usefixtures("local_environments")
def test_session_export_handles_dependency_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    continue_on_error: bool,
) -> None:
    paths = [tmp_path / f"{name}.py" for name in ("first", "second", "third")]
    for path in paths:
        write_notebook(path)
    sync = backends.sync_notebook_async

    async def fail_second(path: str, *, backend: Backend) -> Environment:
        if Path(path).stem == "second":
            raise click.ClickException("Dependency resolution failed")
        return await sync(path, backend=backend)

    monkeypatch.setattr(backends, "sync_notebook_async", fail_second)
    result = CliRunner().invoke(
        session.session,
        [
            str(tmp_path),
            "--sandbox",
            "--continue-on-error"
            if continue_on_error
            else "--no-continue-on-error",
            "--",
            "--value=forwarded",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert "Dependency resolution failed" in result.output
    assert {path.stem for path in tmp_path.glob("*.json")} == (
        {"first", "third"} if continue_on_error else {"first"}
    )
    assert [get_session_cache_file(path).exists() for path in paths] == [
        True,
        False,
        continue_on_error,
    ]


@pytest.mark.parametrize(
    "options", [["--no-sandbox"], ["--sandbox=pixi", "--no-sandbox"]]
)
def test_session_export_does_not_require_a_backend(
    temp_marimo_file: str,
    monkeypatch: pytest.MonkeyPatch,
    options: list[str],
) -> None:
    def unavailable(_: Backend) -> None:
        raise AssertionError(
            "Non-sandboxed exports must not require a backend"
        )

    monkeypatch.setattr(backends, "ensure_available", unavailable)
    result = CliRunner().invoke(session.session, [temp_marimo_file, *options])
    assert result.exit_code == 0, result.output
    assert get_session_cache_file(Path(temp_marimo_file)).exists()


def test_thumbnail_sandbox_requires_execution(tmp_path: Path) -> None:
    path = tmp_path / "notebook.py"
    write_notebook(path)
    result = CliRunner().invoke(thumbnail.thumbnail, [str(path), "--sandbox"])
    assert result.exit_code != 0
    assert "--sandbox requires --execute" in result.output


def test_session_export_reports_invalid_worker_output(
    temp_marimo_file: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        session, "run_python_subprocess", AsyncMock(return_value="not json")
    )
    result = CliRunner().invoke(
        session.session, [temp_marimo_file, "--sandbox"]
    )
    assert result.exit_code == 1
    assert "Failed to parse sandbox session export output" in result.output
    assert not get_session_cache_file(Path(temp_marimo_file)).exists()


@pytest.mark.parametrize("export_format", ["session", "thumbnail"])
@pytest.mark.parametrize("backend", ["uv", "pixi"])
def test_export_reports_missing_selected_backend(
    export_format: str,
    backend: Backend,
    temp_marimo_file: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    command = (
        session.session if export_format == "session" else thumbnail.thumbnail
    )
    args = [temp_marimo_file, f"--sandbox={backend}"]
    if export_format == "thumbnail":
        args.append("--execute")
    result = CliRunner().invoke(command, args)
    assert result.exit_code == 1
    assert f"{backend} must be installed" in result.output
