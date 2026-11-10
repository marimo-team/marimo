# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import click
import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo._cli.cli import main
from marimo._cli.config.overrides import parse_config_overrides
from marimo._cli.config.utils import format_config_docs
from marimo._config.config_schema import MarimoConfig, ServerConfig
from marimo._config.manager import (
    CLIConfigReader,
    ScriptConfigReader,
    get_default_config_manager,
)
from marimo._config.schema_utils import config_cli_flags, config_leaf_types
from marimo._config.utils import get_user_config_path
from marimo._server.workspace import DirectoryWorkspace

if TYPE_CHECKING:
    from collections.abc import Iterator


pytestmark = pytest.mark.usefixtures("clean_config_environment")


@pytest.fixture
def config_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".marimo.toml").write_text("")
    get_user_config_path.cache_clear()
    yield tmp_path
    get_user_config_path.cache_clear()


def parse(*values: str) -> dict[str, Any]:
    return parse_config_overrides(
        click.Context(click.Command("test")),
        click.Option(["--config"]),
        values,
    )


def test_parse_config_overrides() -> None:
    assert parse(
        "display.theme=dark",
        "server.port=8080",
        "server.headless=true",
        "server.timeout=1.5",
        "server.session_ttl=null",
        "runtime.pythonpath='path with spaces' other",
        "runtime.default_auto_download=html ipynb",
        "runtime.dotenv=",
        'keymap.overrides={"run-cell": "Ctrl-Enter"}',
        "ai.open_ai.api_key=contains=equals",
        "display.theme=light",
    ) == snapshot(
        {
            "display": {"theme": "light"},
            "server": {
                "port": 8080,
                "headless": True,
                "timeout": 1.5,
                "session_ttl": None,
            },
            "runtime": {
                "pythonpath": ["path with spaces", "other"],
                "default_auto_download": ["html", "ipynb"],
                "dotenv": [],
            },
            "keymap": {"overrides": {"run-cell": "Ctrl-Enter"}},
            "ai": {"open_ai": {"api_key": "contains=equals"}},
        }
    )


@pytest.mark.parametrize(
    ("assignment", "expected"),
    [
        (
            'runtime.dotenv=[".env", ".env.local"]',
            {"runtime": {"dotenv": [".env", ".env.local"]}},
        ),
        (
            'runtime.pythonpath=["./shared libraries", "./src"]',
            {"runtime": {"pythonpath": ["./shared libraries", "./src"]}},
        ),
        ("runtime.dotenv=[]", {"runtime": {"dotenv": []}}),
        (
            'runtime.default_auto_download=["html", "ipynb"]',
            {"runtime": {"default_auto_download": ["html", "ipynb"]}},
        ),
        (
            'file_browser.folders=[{"path":"/data","name":"Data"}]',
            {"file_browser": {"folders": [{"path": "/data", "name": "Data"}]}},
        ),
        (
            'cache.store={"type":"file","args":{}}',
            {"cache": {"store": {"type": "file", "args": {}}}},
        ),
        (
            'mcp.mcpServers={"local":{"command":"example"}}',
            {"mcp": {"mcpServers": {"local": {"command": "example"}}}},
        ),
    ],
)
def test_structured_overrides(
    assignment: str, expected: dict[str, Any]
) -> None:
    assert parse(assignment) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("display.theme", "Expected category.name=value"),
        ("display.them=dark", "Did you mean 'display.theme'?"),
        ("display=dark", "Unknown configuration field 'display'"),
        ("server.port=secret-value", "Invalid value for 'server.port'"),
        (
            "server.headless=secret-value",
            "Invalid value for 'server.headless'",
        ),
        ("display.theme=secret-value", "Invalid value for 'display.theme'"),
        ("runtime.default_auto_download=secret-value", "Invalid value"),
        ("runtime.pythonpath='secret-value", "Invalid value"),
        ("runtime.sql_default_limit=-1", "Invalid value"),
        ("runtime.pythonpath=[1]", "Invalid value"),
        ('runtime.default_auto_download=["secret-value"]', "Invalid value"),
        ("mcp.mcpServers=secret-value", "Invalid value"),
    ],
)
def test_invalid_overrides(value: str, message: str) -> None:
    result = CliRunner().invoke(main, ["new", "--config", value])
    assert result.exit_code == 2
    assert message in result.output
    assert "secret-value" not in result.output


def test_cli_metadata() -> None:
    flags = config_cli_flags(MarimoConfig)
    assert flags[("server", "port")] == ("--port", "-p")
    assert flags.keys() <= config_leaf_types(MarimoConfig).keys()
    spellings = [flag for names in flags.values() for flag in names]
    assert len(spellings) == len(set(spellings))
    docs = format_config_docs(ServerConfig)
    assert "CLI flag: --port, -p" in docs
    assert "CLI flag: --token, --no-token" in docs


def test_cli_layer_is_ephemeral_and_wins_over_session_metadata(
    config_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = config_directory / ".marimo.toml"
    config_path.write_text('[display]\ntheme = "light"\n')
    notebook = config_directory / "notebook.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.display]\n# theme = "light"\n# ///\n'
    )
    monkeypatch.setenv("MARIMO_DISPLAY_THEME", "light")
    manager = get_default_config_manager(current_path=str(notebook))
    manager = manager.with_partial(
        CLIConfigReader(parse("display.theme=dark"))
    )
    manager = manager.with_partial(ScriptConfigReader(str(notebook)))
    resolved = manager.get_config_with_sources()
    assert resolved.config["display"]["theme"] == "dark"
    assert resolved.origins[("display", "theme")] == "cli"
    assert config_path.read_text() == '[display]\ntheme = "light"\n'
    assert (
        get_default_config_manager(current_path=str(notebook))
        .get_config()
        .display.theme
        == "light"
    )


def test_override_redaction(config_directory: Path) -> None:
    before = (config_directory / ".marimo.toml").read_bytes()
    manager = get_default_config_manager(current_path=str(config_directory))
    manager = manager.with_partial(
        CLIConfigReader(parse("server.token_password=secret-value"))
    )
    assert manager.get_config().server.token_password == "********"
    assert (
        manager.get_config(hide_secrets=False).server.token_password
        == "secret-value"
    )
    assert (config_directory / ".marimo.toml").read_bytes() == before


@pytest.fixture
def launch(config_directory: Path, monkeypatch: pytest.MonkeyPatch) -> Mock:
    (config_directory / "notebook.py").write_text(
        "import marimo\napp = marimo.App()\n"
    )
    monkeypatch.setenv("MARIMO_SERVER_SKIP_UPDATE_CHECK", "true")
    monkeypatch.setattr(
        "marimo._cli.sandbox.ensure_server_environment",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "marimo._utils.platform.check_shared_memory_available",
        lambda: (True, None),
    )
    start = Mock()
    monkeypatch.setattr("marimo._cli.cli.start", start)
    return start


@pytest.mark.parametrize("command", ["edit", "new", "run"])
def test_launch_defaults(command: str, launch: Mock) -> None:
    args = [command, "--no-sandbox"]
    if command != "new":
        args.append("notebook.py")
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    kwargs = launch.call_args.kwargs
    assert kwargs["config_manager"].get_config().server == ServerConfig(
        skip_update_check=True
    )
    assert not {
        "host",
        "port",
        "headless",
        "ttl_seconds",
        "include_code",
        "redirect_console_to_browser",
        "auth_token",
    }.intersection(kwargs)


@pytest.mark.parametrize("command", ["edit", "new", "run"])
@pytest.mark.parametrize("flag_first", [True, False])
def test_launch_shortcuts_win(
    command: str,
    flag_first: bool,
    launch: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MARIMO_SERVER_PORT", "7000")
    flags = ["--port", "9000", "--no-token", "--no-skew-protection"]
    overrides = [
        "--config",
        "server.port=8000",
        "--config",
        "server.token=true",
        "--config",
        "server.headless=true",
        "--config",
        "server.session_ttl=null",
        "--config",
        "server.base_url=/app",
        "--config",
        "display.theme=dark",
        "--config",
        "server.allow_origins=https://a.example https://b.example",
    ]
    args = [
        command,
        "--no-sandbox",
        *(flags + overrides if flag_first else overrides + flags),
    ]
    if command != "new":
        args.append("notebook.py")
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    kwargs = launch.call_args.kwargs
    server = kwargs["config_manager"].get_config().server
    assert server == ServerConfig(
        port=9000,
        headless=True,
        session_ttl=None,
        token=False,
        base_url="/app",
        allow_origins=["https://a.example", "https://b.example"],
        skew_protection=False,
        skip_update_check=True,
    )
    resolved = kwargs["config_manager"].get_config_with_sources()
    assert resolved.config["display"]["theme"] == "dark"
    assert resolved.origins[("server", "port")] == "cli"


@pytest.mark.parametrize("source", ["flag", "override", "environment", "file"])
def test_edit_reserves_password_stdin_from_resolved_config(
    source: str,
    launch: Mock,
    config_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: list[str] = []
    if source == "flag":
        options = ["--token-password-file", "-"]
    elif source == "override":
        options = ["--config", "server.token_password_file=-"]
    elif source == "environment":
        monkeypatch.setenv("MARIMO_SERVER_TOKEN_PASSWORD_FILE", "-")
    else:
        (config_directory / ".marimo.toml").write_text(
            '[server]\ntoken_password_file = "-"\n'
        )
        monkeypatch.setattr(
            "marimo._config.manager.is_trusted_user_config_path",
            lambda _path: True,
        )
    read_notebook_stdin = Mock(
        side_effect=AssertionError("Password input is not notebook code")
    )
    monkeypatch.setattr(
        "marimo._cli.cli._get_stdin_contents", read_notebook_stdin
    )

    result = CliRunner().invoke(
        main, ["edit", "--no-sandbox", *options], input="password"
    )

    assert result.exit_code == 0, result.output
    read_notebook_stdin.assert_not_called()
    manager = launch.call_args.kwargs["config_manager"]
    assert (
        manager.get_config(hide_secrets=False).server.token_password_file
        == "-"
    )


@pytest.mark.parametrize("command", ["edit", "run"])
@pytest.mark.parametrize("source", ["flag", "override", "environment", "file"])
def test_docker_port_uses_resolved_config(
    command: str,
    source: str,
    config_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (config_directory / ".marimo.toml").write_text("[server]\nport = 6000\n")
    options: list[str] = []
    expected = 6000
    if source != "file":
        monkeypatch.setenv("MARIMO_SERVER_PORT", "7000")
        expected = 7000
    if source in ("override", "flag"):
        options += ["--config", "server.port=8000"]
        expected = 8000
    if source == "flag":
        options += ["--port", "9000"]
        expected = 9000
    monkeypatch.setattr(
        "marimo._cli.cli.prompt_run_in_docker_container",
        lambda *_args, **_kwargs: True,
    )
    docker = Mock()
    monkeypatch.setattr("marimo._cli.run_docker.run_in_docker", docker)
    validate = Mock(
        side_effect=AssertionError("The container downloads remote notebooks")
    )
    monkeypatch.setattr("marimo._cli.cli.validate_name", validate)

    result = CliRunner().invoke(
        main, [command, "https://example.com/notebook.py", *options]
    )

    assert result.exit_code == 0, result.output
    docker.assert_called_once()
    assert docker.call_args.kwargs["port"] == expected
    validate.assert_not_called()


@pytest.mark.parametrize("command", ["edit", "new", "run", "tutorial"])
@pytest.mark.parametrize("flag", ["--port", "-p"])
@pytest.mark.parametrize("port", [-1, 65536, 70000])
def test_invalid_port_stops_during_argument_parsing(
    command: str, flag: str, port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = Mock()
    preflight = Mock(side_effect=AssertionError("Command body must not run"))
    monkeypatch.setattr("marimo._cli.cli.start", start)
    monkeypatch.setattr("marimo._cli.cli.resolve_cli_config", preflight)
    args = [command, flag, str(port)]
    if command in ("edit", "run"):
        args.append("notebook.py")
    elif command == "tutorial":
        args.append("intro")

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 2, result.output
    assert "0<=x<=65535" in result.output
    assert "Traceback" not in result.output
    preflight.assert_not_called()
    start.assert_not_called()


@pytest.mark.parametrize("command", ["edit", "new", "run"])
@pytest.mark.parametrize("port", [-1, 65536, 70000])
def test_invalid_config_port_stops_during_argument_parsing(
    command: str, port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = Mock(side_effect=AssertionError("Command body must not run"))
    monkeypatch.setattr("marimo._cli.cli.resolve_cli_config", preflight)
    args = [command, "--config", f"server.port={port}"]
    if command != "new":
        args.append("notebook.py")

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 2, result.output
    assert "Invalid value for 'server.port'" in result.output
    preflight.assert_not_called()


@pytest.mark.parametrize("command", ["edit", "new", "run", "tutorial"])
@pytest.mark.parametrize("port", [0, 65535])
def test_port_boundaries_are_accepted(command: str, port: int) -> None:
    parent = click.Context(main)
    cli_command = main.get_command(parent, command)
    assert cli_command is not None
    args = ["--port", str(port)]
    if command in ("edit", "run"):
        args.append("notebook.py")
    elif command == "tutorial":
        args.append("intro")
    with cli_command.make_context(command, args, parent=parent) as ctx:
        assert ctx.params["port"] == port
    assert parse(f"server.port={port}") == {"server": {"port": port}}


def test_tutorial_disables_watch_and_console_redirection(
    launch: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARIMO_SERVER_WATCH", "true")
    monkeypatch.setenv("MARIMO_SERVER_REDIRECT_CONSOLE_TO_BROWSER", "true")
    result = CliRunner().invoke(main, ["tutorial", "intro"])
    assert result.exit_code == 0, result.output
    server = launch.call_args.kwargs["config_manager"].get_config().server
    assert (server.watch, server.redirect_console_to_browser) == (False, False)


@pytest.mark.parametrize("command", ["edit", "run"])
def test_config_overrides_preserve_notebook_arguments(
    command: str, launch: Mock
) -> None:
    notebook_args = [
        "--lr",
        "1e-4",
        "--epochs",
        "15",
        "--config",
        "notebook-value",
    ]
    result = CliRunner().invoke(
        main,
        [
            command,
            "--no-sandbox",
            "notebook.py",
            "--config",
            "display.theme=dark",
            "--",
            *notebook_args,
        ],
    )
    assert result.exit_code == 0, result.output
    kwargs = launch.call_args.kwargs
    assert kwargs["cli_args"] == {
        "lr": 1e-4,
        "epochs": 15,
        "config": "notebook-value",
    }
    assert kwargs["argv"] == notebook_args
    assert kwargs["config_manager"].get_config().display.theme == "dark"


@pytest.mark.parametrize(
    ("paths", "workspace_root"),
    [
        (["project/a.py", "project/b.py"], "project"),
        (["project", "project/a.py"], "project"),
        (["project/a.py", "other/b.py"], None),
    ],
)
@pytest.mark.parametrize("override_theme", [False, True])
def test_multi_file_run_uses_workspace_configuration(
    paths: list[str],
    workspace_root: str | None,
    override_theme: bool,
    launch: Mock,
    config_directory: Path,
) -> None:
    (config_directory / "pyproject.toml").write_text(
        '[tool.marimo.display]\ntheme = "light"\n'
    )
    for directory in ("project", "other"):
        project = config_directory / directory
        project.mkdir()
        (project / "pyproject.toml").write_text(
            '[tool.marimo.display]\ntheme = "dark"\n'
        )
        for name in ("a.py", "b.py"):
            (project / name).write_text("import marimo\napp = marimo.App()\n")
    options = ["--config", "display.theme=light"] if override_theme else []
    result = CliRunner().invoke(
        main, ["run", "--no-sandbox", *options, *paths]
    )
    assert result.exit_code == 0, result.output
    kwargs = launch.call_args.kwargs
    directory = kwargs["workspace"].directory
    assert {
        "workspace_root": str(Path(directory).resolve())
        if directory
        else None,
        "theme": kwargs["config_manager"].get_config().display.theme,
    } == {
        "workspace_root": str((config_directory / workspace_root).resolve())
        if workspace_root
        else None,
        "theme": "dark" if workspace_root and not override_theme else "light",
    }


def test_configured_directory_watch_does_not_scan_snapshot(
    launch: Mock, config_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = config_directory / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.marimo.server]\nwatch = true\n"
    )
    scan = Mock(
        side_effect=AssertionError("Watch mode must discover notebooks lazily")
    )
    monkeypatch.setattr("marimo._cli.cli._collect_marimo_files", scan)
    result = CliRunner().invoke(main, ["run", "--no-sandbox", "project"])
    assert result.exit_code == 0, result.output
    assert isinstance(launch.call_args.kwargs["workspace"], DirectoryWorkspace)
    scan.assert_not_called()
