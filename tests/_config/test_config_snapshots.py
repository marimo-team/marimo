"""Behavioral baselines for config refactors.

Run this suite on main and on a refactor branch without updating snapshots.
Only temporary directory prefixes are normalized; config values, missing keys,
secret placeholders, and serialized TOML remain part of the comparison.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from inline_snapshot import snapshot

from marimo._config import manager as config_module
from marimo._config.config import DEFAULT_CONFIG
from marimo._config.manager import (
    EnvConfigManager,
    ProjectConfigManager,
    ScriptConfigManager,
    get_default_config_manager,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.utils import (
    get_or_create_user_config_path,
    get_user_config_path,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._config.config import PartialMarimoConfig


@pytest.fixture
def config_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Keep discovery, enforcement, and environment inputs local to each test."""
    root = tmp_path.resolve()
    home = root / "home"
    project = home / "project"
    project.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "xdg"))
    monkeypatch.chdir(project)
    monkeypatch.delenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", raising=False
    )
    monkeypatch.delenv("MARIMO_SERVER_TRANSPORT", raising=False)
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", False)
    # These defaults are inferred at module import, before fixture isolation.
    # Package-manager inference has its own suite in test_config_packages.py.
    monkeypatch.setitem(
        DEFAULT_CONFIG, "package_management", {"manager": "pip"}
    )
    monkeypatch.setitem(
        DEFAULT_CONFIG,
        "runtime",
        {
            **DEFAULT_CONFIG["runtime"],
            "output_max_bytes": 8_000_000,
            "std_stream_max_bytes": 1_000_000,
        },
    )
    get_user_config_path.cache_clear()
    original_path = get_or_create_user_config_path

    def isolated_config_path() -> str:
        # Fail before discovery or persistence if a test loses its isolation.
        assert Path.cwd().is_relative_to(root)
        assert Path(os.environ["HOME"]).is_relative_to(root)
        assert Path(os.environ["XDG_CONFIG_HOME"]).is_relative_to(root)
        path = original_path()
        assert Path(path).resolve().is_relative_to(root)
        return path

    monkeypatch.setattr(
        config_module, "get_or_create_user_config_path", isolated_config_path
    )
    yield root
    get_user_config_path.cache_clear()


def normalized(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {key: normalized(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item, root) for item in value]
    if isinstance(value, str):
        if str(root) + os.sep in value:
            return value.replace(str(root) + os.sep, "<root>/").replace(
                "\\", "/"
            )
        return value
    return value


def write_script(path: Path, settings: str) -> None:
    metadata = "\n".join("# " + line for line in settings.splitlines())
    path.write_text(
        f"# /// script\n{metadata}\n# ///\nimport marimo\napp = marimo.App()\n",
        encoding="utf-8",
    )


def test_default_configuration_snapshot(config_tree: Path) -> None:
    manager = get_default_config_manager(current_path=None)
    assert normalized(
        manager.get_config(hide_secrets=False), config_tree
    ) == snapshot(
        {
            "display": {
                "theme": "light",
                "code_editor_font_size": 14,
                "cell_output": "below",
                "default_width": "medium",
                "dataframes": "rich",
                "default_table_page_size": 10,
                "default_table_max_columns": 50,
                "reference_highlighting": True,
                "code_lens": True,
            },
            "runtime": {
                "dotenv": ["<root>/home/project/.env"],
                "watcher_on_save": "lazy",
                "auto_reload": "off",
                "default_csv_encoding": "utf-8",
                "reactive_tests": True,
                "auto_instantiate": False,
                "on_cell_change": "autorun",
                "default_sql_output": "auto",
                "output_max_bytes": 8000000,
                "std_stream_max_bytes": 1000000,
                "show_tracebacks": False,
            },
            "ai": {
                "enabled": True,
                "allow_provider_config": True,
                "models": {"displayed_models": [], "custom_models": []},
                "custom_providers": {},
            },
            "language_servers": {
                "pylsp": {
                    "enabled": False,
                    "enable_mypy": True,
                    "enable_ruff": True,
                    "enable_flake8": False,
                    "enable_pydocstyle": False,
                    "enable_pylint": False,
                    "enable_pyflakes": False,
                }
            },
            "formatting": {"line_length": 79},
            "completion": {
                "activate_on_typing": True,
                "signature_hint_on_typing": False,
                "copilot": False,
                "auto_close_pairs": True,
            },
            "snippets": {"custom_paths": [], "include_default_snippets": True},
            "keymap": {"preset": "default", "overrides": {}},
            "mcp": {"mcpServers": {}, "presets": []},
            "package_management": {"manager": "pip"},
            "save": {
                "autosave": "after_delay",
                "autosave_delay": 1000,
                "format_on_save": False,
            },
            "server": {"browser": "default", "follow_symlink": False},
            "diagnostics": {"sql_linter": True},
        }
    )
    assert normalized(
        manager.get_config_overrides(hide_secrets=False), config_tree
    ) == snapshot({})
    assert normalized(
        manager.get_config_defaults(hide_secrets=False), config_tree
    ) == snapshot({"runtime": {"dotenv": ["<root>/home/project/.env"]}})


def test_layered_configuration_snapshot(
    config_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = config_tree / "home" / "project"
    user_path = config_tree / "home" / ".marimo.toml"
    user_path.write_text(
        '[display]\ntheme = "dark"\ndefault_width = "full"\n'
        '[runtime]\nauto_instantiate = false\ndotenv = ["user.env"]\n'
        "[formatting]\nline_length = 70\n"
        '[ai.open_ai]\napi_key = "user-secret"\n'
        '[signing]\nprivate_key_path = "user.key"\n',
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.marimo.display]\ntheme = "light"\ncustom_css = ["style.css"]\n'
        '[tool.marimo.runtime]\npythonpath = ["src"]\ndotenv = ["project.env"]\n'
        "[tool.marimo.formatting]\nline_length = 90\n"
        '[tool.marimo.keymap]\nvimrc = "editor.vim"\n'
        '[tool.marimo.ai.open_ai]\napi_key = "project-secret"\n',
        encoding="utf-8",
    )
    notebook = project / "notebooks" / "app.py"
    notebook.parent.mkdir()
    write_script(
        notebook,
        "[tool.marimo.formatting]\nline_length = 110\n"
        '[tool.marimo.runtime]\nauto_instantiate = false\ndotenv = ["script.env"]\n'
        '[tool.marimo.display]\ndefault_width = "columns"\ncustom_css = ["ignored.css"]\n'
        "[tool.marimo.experimental]\nisolate_apps = true\n"
        '[tool.marimo.ai.open_ai]\napi_key = "ignored-script-secret"\n',
    )
    monkeypatch.setenv(
        "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", "true"
    )
    monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", "sse")
    manager = get_default_config_manager(
        current_path=str(notebook)
    ).with_overrides(
        {
            "formatting": {"line_length": 130},
            "sharing": {"html": True, "wasm": True, "molab": True},
        }
    )
    monkeypatch.setattr(GLOBAL_SETTINGS, "RESTRICT_SHARING", True)
    # Masked reads must not mutate the following unmasked reads.
    views = {
        "resolved_masked": manager.get_config(),
        "resolved_unmasked": manager.get_config(hide_secrets=False),
        "user_masked": manager.get_user_config(),
        "overrides_unmasked": manager.get_config_overrides(hide_secrets=False),
        "script_unmasked": ScriptConfigManager(str(notebook)).get_config(
            hide_secrets=False
        ),
    }
    assert normalized(views, config_tree) == snapshot(
        {
            "resolved_masked": {
                "language_servers": {
                    "pylsp": {
                        "enabled": False,
                        "enable_mypy": True,
                        "enable_ruff": True,
                        "enable_flake8": False,
                        "enable_pydocstyle": False,
                        "enable_pylint": False,
                        "enable_pyflakes": False,
                    }
                },
                "completion": {
                    "activate_on_typing": True,
                    "signature_hint_on_typing": False,
                    "copilot": False,
                    "auto_close_pairs": True,
                },
                "experimental": {},
                "signing": {"private_key_path": "********"},
                "mcp": {"mcpServers": {}, "presets": []},
                "runtime": {
                    "dotenv": [],
                    "watcher_on_save": "lazy",
                    "auto_reload": "off",
                    "default_csv_encoding": "utf-8",
                    "reactive_tests": True,
                    "auto_instantiate": True,
                    "on_cell_change": "autorun",
                    "pythonpath": ["<root>/home/project/src"],
                    "default_sql_output": "auto",
                    "output_max_bytes": 8000000,
                    "std_stream_max_bytes": 1000000,
                    "show_tracebacks": False,
                },
                "server": {
                    "follow_symlink": False,
                    "browser": "default",
                    "transport": "sse",
                },
                "snippets": {
                    "custom_paths": [],
                    "include_default_snippets": True,
                },
                "save": {
                    "autosave": "after_delay",
                    "autosave_delay": 1000,
                    "format_on_save": False,
                },
                "package_management": {"manager": "pip"},
                "diagnostics": {"sql_linter": True},
                "display": {
                    "dataframes": "rich",
                    "theme": "light",
                    "code_lens": True,
                    "custom_css": ["<root>/home/project/style.css"],
                    "default_width": "columns",
                    "code_editor_font_size": 14,
                    "default_table_max_columns": 50,
                    "reference_highlighting": True,
                    "default_table_page_size": 10,
                    "cell_output": "below",
                },
                "ai": {
                    "models": {"displayed_models": [], "custom_models": []},
                    "enabled": True,
                    "custom_providers": {},
                    "open_ai": {"api_key": "********"},
                    "allow_provider_config": True,
                },
                "sharing": {"molab": False, "html": False, "wasm": False},
                "keymap": {
                    "overrides": {},
                    "vimrc": "<root>/home/project/editor.vim",
                    "preset": "default",
                },
                "formatting": {"line_length": 130},
            },
            "resolved_unmasked": {
                "language_servers": {
                    "pylsp": {
                        "enabled": False,
                        "enable_mypy": True,
                        "enable_ruff": True,
                        "enable_flake8": False,
                        "enable_pydocstyle": False,
                        "enable_pylint": False,
                        "enable_pyflakes": False,
                    }
                },
                "completion": {
                    "activate_on_typing": True,
                    "signature_hint_on_typing": False,
                    "copilot": False,
                    "auto_close_pairs": True,
                },
                "experimental": {},
                "signing": {"private_key_path": "user.key"},
                "mcp": {"mcpServers": {}, "presets": []},
                "runtime": {
                    "dotenv": ["<root>/home/project/script.env"],
                    "watcher_on_save": "lazy",
                    "auto_reload": "off",
                    "default_csv_encoding": "utf-8",
                    "reactive_tests": True,
                    "auto_instantiate": True,
                    "on_cell_change": "autorun",
                    "pythonpath": ["<root>/home/project/src"],
                    "default_sql_output": "auto",
                    "output_max_bytes": 8000000,
                    "std_stream_max_bytes": 1000000,
                    "show_tracebacks": False,
                },
                "server": {
                    "follow_symlink": False,
                    "browser": "default",
                    "transport": "sse",
                },
                "snippets": {
                    "custom_paths": [],
                    "include_default_snippets": True,
                },
                "save": {
                    "autosave": "after_delay",
                    "autosave_delay": 1000,
                    "format_on_save": False,
                },
                "package_management": {"manager": "pip"},
                "diagnostics": {"sql_linter": True},
                "display": {
                    "dataframes": "rich",
                    "theme": "light",
                    "code_lens": True,
                    "custom_css": ["<root>/home/project/style.css"],
                    "default_width": "columns",
                    "code_editor_font_size": 14,
                    "default_table_max_columns": 50,
                    "reference_highlighting": True,
                    "default_table_page_size": 10,
                    "cell_output": "below",
                },
                "ai": {
                    "models": {"displayed_models": [], "custom_models": []},
                    "enabled": True,
                    "custom_providers": {},
                    "open_ai": {"api_key": "project-secret"},
                    "allow_provider_config": True,
                },
                "sharing": {"molab": False, "html": False, "wasm": False},
                "keymap": {
                    "overrides": {},
                    "vimrc": "<root>/home/project/editor.vim",
                    "preset": "default",
                },
                "formatting": {"line_length": 130},
            },
            "user_masked": {
                "package_management": {"manager": "pip"},
                "display": {
                    "dataframes": "rich",
                    "theme": "dark",
                    "code_lens": True,
                    "default_width": "full",
                    "code_editor_font_size": 14,
                    "default_table_max_columns": 50,
                    "reference_highlighting": True,
                    "default_table_page_size": 10,
                    "cell_output": "below",
                },
                "ai": {
                    "models": {"displayed_models": [], "custom_models": []},
                    "open_ai": {"api_key": "********"},
                    "enabled": True,
                    "custom_providers": {},
                    "allow_provider_config": True,
                },
                "language_servers": {
                    "pylsp": {
                        "enabled": False,
                        "enable_mypy": True,
                        "enable_ruff": True,
                        "enable_flake8": False,
                        "enable_pydocstyle": False,
                        "enable_pylint": False,
                        "enable_pyflakes": False,
                    }
                },
                "signing": {"private_key_path": "********"},
                "formatting": {"line_length": 70},
                "completion": {
                    "activate_on_typing": True,
                    "signature_hint_on_typing": False,
                    "copilot": False,
                    "auto_close_pairs": True,
                },
                "snippets": {
                    "custom_paths": [],
                    "include_default_snippets": True,
                },
                "keymap": {"preset": "default", "overrides": {}},
                "mcp": {"mcpServers": {}, "presets": []},
                "runtime": {
                    "watcher_on_save": "lazy",
                    "output_max_bytes": 8000000,
                    "auto_reload": "off",
                    "default_csv_encoding": "utf-8",
                    "dotenv": [],
                    "reactive_tests": True,
                    "auto_instantiate": False,
                    "default_sql_output": "auto",
                    "on_cell_change": "autorun",
                    "std_stream_max_bytes": 1000000,
                    "show_tracebacks": False,
                },
                "save": {
                    "autosave": "after_delay",
                    "autosave_delay": 1000,
                    "format_on_save": False,
                },
                "server": {"browser": "default", "follow_symlink": False},
                "diagnostics": {"sql_linter": True},
            },
            "overrides_unmasked": {
                "display": {
                    "theme": "light",
                    "default_width": "columns",
                    "custom_css": ["<root>/home/project/style.css"],
                },
                "experimental": {},
                "ai": {"open_ai": {"api_key": "project-secret"}},
                "sharing": {"molab": False, "html": False, "wasm": False},
                "formatting": {"line_length": 130},
                "keymap": {"vimrc": "<root>/home/project/editor.vim"},
                "runtime": {
                    "dotenv": ["<root>/home/project/script.env"],
                    "auto_instantiate": True,
                    "pythonpath": ["<root>/home/project/src"],
                },
                "server": {"transport": "sse"},
            },
            "script_unmasked": {
                "formatting": {"line_length": 110},
                "runtime": {"dotenv": ["<root>/home/project/script.env"]},
                "display": {"default_width": "columns"},
                "experimental": {},
            },
        }
    )


def test_dotenv_fallbacks_snapshot(config_tree: Path) -> None:
    project = config_tree / "home" / "project"
    notebook = project / "notebooks" / "app.py"
    notebook.parent.mkdir()
    write_script(notebook, "[tool.marimo.formatting]\nline_length = 100")
    cases: dict[str, Any] = {}
    for name, current_path in [
        ("directory", project),
        ("standalone_notebook", notebook),
        ("home", config_tree / "home"),
    ]:
        manager = get_default_config_manager(current_path=str(current_path))
        cases[name] = {
            "defaults": manager.get_config_defaults(hide_secrets=False),
            "dotenv": manager.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            ),
            "masked_dotenv": manager.get_config()["runtime"].get("dotenv"),
            "overrides": manager.get_config_overrides(hide_secrets=False),
        }
    (project / "pyproject.toml").write_text(
        '[project]\nname = "example"\n', encoding="utf-8"
    )
    manager = get_default_config_manager(current_path=str(notebook))
    cases["project_notebook"] = {
        "defaults": manager.get_config_defaults(hide_secrets=False)
    }
    home_config = config_tree / "home" / ".marimo.toml"
    for name, setting in [
        ("explicit_user", '["chosen.env"]'),
        ("masked_empty_user", "[]"),
    ]:
        home_config.write_text(
            f"[runtime]\ndotenv = {setting}\n", encoding="utf-8"
        )
        get_user_config_path.cache_clear()
        manager = get_default_config_manager(current_path=str(notebook))
        cases[name] = {
            "dotenv": manager.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            )
        }
    assert normalized(cases, config_tree) == snapshot(
        {
            "directory": {
                "defaults": {
                    "runtime": {"dotenv": ["<root>/home/project/.env"]}
                },
                "dotenv": ["<root>/home/project/.env"],
                "masked_dotenv": [],
                "overrides": {},
            },
            "standalone_notebook": {
                "defaults": {
                    "runtime": {
                        "dotenv": ["<root>/home/project/notebooks/.env"]
                    }
                },
                "dotenv": ["<root>/home/project/notebooks/.env"],
                "masked_dotenv": [],
                "overrides": {"formatting": {"line_length": 100}},
            },
            "home": {
                "defaults": {},
                "dotenv": None,
                "masked_dotenv": None,
                "overrides": {},
            },
            "project_notebook": {
                "defaults": {
                    "runtime": {"dotenv": ["<root>/home/project/.env"]}
                }
            },
            "explicit_user": {"dotenv": ["chosen.env"]},
            "masked_empty_user": {"dotenv": ["<root>/home/project/.env"]},
        }
    )


def test_discovery_snapshot(config_tree: Path) -> None:
    project = config_tree / "home" / "project"
    nested = project / "nested"
    nested.mkdir()
    xdg = config_tree / "xdg" / "marimo" / "marimo.toml"
    xdg.parent.mkdir(parents=True)
    paths = [
        xdg,
        config_tree / "home" / ".marimo.toml",
        project / ".marimo.toml",
        nested / ".marimo.toml",
    ]
    cases: dict[str, Any] = {}
    for name, path in zip(
        ("xdg", "home", "parent", "cwd"), paths, strict=True
    ):
        path.write_text('[display]\ntheme = "dark"\n', encoding="utf-8")
        # Exercise public discovery through the default manager.
        with pytest.MonkeyPatch.context() as patch:
            patch.chdir(nested)
            get_user_config_path.cache_clear()
            manager = get_default_config_manager(current_path=None)
            cases[name] = manager.user_config_mgr.get_config_path()
    assert normalized(cases, config_tree) == snapshot(
        {
            "xdg": "<root>/xdg/marimo/marimo.toml",
            "home": "<root>/home/.marimo.toml",
            "parent": "<root>/home/project/.marimo.toml",
            "cwd": "<root>/home/project/nested/.marimo.toml",
        }
    )


def test_persistence_snapshot(config_tree: Path) -> None:
    path = config_tree / "home" / ".marimo.toml"
    path.write_text(
        '[ai.open_ai]\napi_key = "keep-me"\n[ai]\nmax_tokens = 999\n',
        encoding="utf-8",
    )
    manager = get_default_config_manager(current_path=None)
    # The endpoint accepts deep partial patches and null-as-delete values.
    manager.save_config(
        cast(
            "PartialMarimoConfig",
            {
                "display": {"theme": "dark"},
                "ai": {"open_ai": {"api_key": "********"}, "max_tokens": None},
            },
        )
    )
    first_save = path.read_text(encoding="utf-8")
    manager.save_config(
        cast("PartialMarimoConfig", {"display": {"theme": "dark"}})
    )
    assert path.read_text(encoding="utf-8") == first_save
    assert normalized(first_save, config_tree) == snapshot("""\
[ai]
allow_provider_config = true
enabled = true

[ai.custom_providers]

[ai.models]
custom_models = []
displayed_models = []

[ai.open_ai]
api_key = "keep-me"

[completion]
activate_on_typing = true
auto_close_pairs = true
copilot = false
signature_hint_on_typing = false

[diagnostics]
sql_linter = true

[display]
cell_output = "below"
code_editor_font_size = 14
code_lens = true
dataframes = "rich"
default_table_max_columns = 50
default_table_page_size = 10
default_width = "medium"
reference_highlighting = true
theme = "dark"

[formatting]
line_length = 79

[keymap]
preset = "default"

[keymap.overrides]

[language_servers.pylsp]
enable_flake8 = false
enable_mypy = true
enable_pydocstyle = false
enable_pyflakes = false
enable_pylint = false
enable_ruff = true
enabled = false

[mcp]
presets = []

[mcp.mcpServers]

[package_management]
manager = "pip"

[runtime]
auto_instantiate = false
auto_reload = "off"
default_csv_encoding = "utf-8"
default_sql_output = "auto"
on_cell_change = "autorun"
output_max_bytes = 8000000
reactive_tests = true
show_tracebacks = false
std_stream_max_bytes = 1000000
watcher_on_save = "lazy"

[save]
autosave = "after_delay"
autosave_delay = 1000
format_on_save = false

[server]
browser = "default"
follow_symlink = false

[snippets]
custom_paths = []
include_default_snippets = true
""")
    assert (
        manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
        == "keep-me"
    )
    assert "max_tokens" not in manager.get_config(hide_secrets=False)["ai"]


def test_invalid_and_missing_inputs_snapshot(config_tree: Path) -> None:
    project = config_tree / "home" / "project"
    notebook = project / "app.py"
    cases: dict[str, Any] = {}
    for name, contents in [
        ("missing", None),
        ("empty", ""),
        ("malformed", "[tool.marimo\n"),
        ("no_marimo", '[project]\nname = "example"\n'),
    ]:
        pyproject = project / "pyproject.toml"
        if contents is not None:
            pyproject.write_text(contents, encoding="utf-8")
        cases[name] = ProjectConfigManager(str(project)).get_config(
            hide_secrets=False
        )
    for name, contents in [
        ("missing_script", None),
        ("no_metadata", "import marimo\n"),
        ("invalid_metadata", "# /// script\n# [tool.marimo\n# ///\n"),
    ]:
        if contents is not None:
            notebook.write_text(contents, encoding="utf-8")
        cases[name] = ScriptConfigManager(str(notebook)).get_config(
            hide_secrets=False
        )
    assert cases == snapshot(
        {
            "missing": {},
            "empty": {},
            "malformed": {},
            "no_marimo": {},
            "missing_script": {},
            "no_metadata": {},
            "invalid_metadata": {},
        }
    )


def test_environment_snapshot(
    config_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del config_tree
    cases: dict[str, Any] = {}
    for transport, instantiate in [
        ("sse", "true"),
        ("websocket", "false"),
        ("invalid", "true"),
    ]:
        monkeypatch.setenv("MARIMO_SERVER_TRANSPORT", transport)
        monkeypatch.setenv(
            "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE", instantiate
        )
        cases[transport] = EnvConfigManager().get_config(hide_secrets=False)
    assert cases == snapshot(
        {
            "sse": {
                "runtime": {"auto_instantiate": True},
                "server": {"transport": "sse"},
            },
            "websocket": {
                "runtime": {"auto_instantiate": False},
                "server": {"transport": "websocket"},
            },
            "invalid": {"runtime": {"auto_instantiate": True}},
        }
    )


def test_trust_origins_snapshot(config_tree: Path) -> None:
    project = config_tree / "home" / "project"
    settings = (
        '[display]\ntheme = "dark"\n'
        '[signing]\nprivate_key_path = "identity.key"\n'
        'trusted_signers = { example = "owner" }\n'
        '[cache]\nverification = "strict"\nstore = "disk"\n'
    )
    home_config = config_tree / "home" / ".marimo.toml"
    home_config.write_text(settings, encoding="utf-8")
    cases: dict[str, Any] = {}
    for name, path in [
        ("home", home_config),
        ("workspace", project / ".marimo.toml"),
    ]:
        path.write_text(settings, encoding="utf-8")
        get_user_config_path.cache_clear()
        config = get_default_config_manager(current_path=None).get_config(
            hide_secrets=False
        )
        cases[name] = {
            "signing": config.get("signing"),
            "cache": config.get("cache"),
        }
    project_file = project / "pyproject.toml"
    project_file.write_text(
        settings.replace("[", "[tool.marimo."), encoding="utf-8"
    )
    cases["pyproject"] = ProjectConfigManager(str(project_file)).get_config(
        hide_secrets=False
    )
    assert cases == snapshot(
        {
            "home": {
                "signing": {
                    "private_key_path": "identity.key",
                    "trusted_signers": {"example": "owner"},
                },
                "cache": {"verification": "strict", "store": "disk"},
            },
            "workspace": {"signing": None, "cache": {}},
            "pyproject": {
                "display": {"theme": "dark", "custom_css": []},
                "cache": {"store": "disk"},
            },
        }
    )


def test_secret_roundtrip_snapshot(config_tree: Path) -> None:
    path = config_tree / "home" / ".marimo.toml"
    path.write_text(
        '[ai.open_ai]\napi_key = "openai-secret"\n'
        '[ai.bedrock]\naws_access_key_id = "access-secret"\n'
        'aws_secret_access_key = "private-secret"\n'
        '[ai.custom_providers.local]\napi_key = "custom-secret"\n'
        '[signing]\nprivate_key_path = "identity.key"\n'
        '[runtime]\ndotenv = ["secrets.env"]\n',
        encoding="utf-8",
    )
    manager = get_default_config_manager(current_path=None)
    masked = manager.get_user_config()
    manager.save_config(masked)
    unmasked = manager.get_user_config(hide_secrets=False)
    assert {
        "masked": {
            key: masked.get(key) for key in ("ai", "runtime", "signing")
        },
        "roundtrip": {
            key: unmasked.get(key) for key in ("ai", "runtime", "signing")
        },
    } == snapshot(
        {
            "masked": {
                "ai": {
                    "enabled": True,
                    "allow_provider_config": True,
                    "custom_providers": {"local": {"api_key": "********"}},
                    "open_ai": {"api_key": "********"},
                    "bedrock": {
                        "aws_access_key_id": "********",
                        "aws_secret_access_key": "********",
                    },
                    "models": {"displayed_models": [], "custom_models": []},
                },
                "runtime": {
                    "dotenv": [],
                    "reactive_tests": True,
                    "auto_instantiate": False,
                    "default_sql_output": "auto",
                    "output_max_bytes": 8000000,
                    "show_tracebacks": False,
                    "default_csv_encoding": "utf-8",
                    "auto_reload": "off",
                    "std_stream_max_bytes": 1000000,
                    "on_cell_change": "autorun",
                    "watcher_on_save": "lazy",
                },
                "signing": {"private_key_path": "********"},
            },
            "roundtrip": {
                "ai": {
                    "custom_providers": {
                        "local": {"api_key": "custom-secret"}
                    },
                    "models": {"custom_models": [], "displayed_models": []},
                    "enabled": True,
                    "allow_provider_config": True,
                    "open_ai": {"api_key": "openai-secret"},
                    "bedrock": {
                        "aws_access_key_id": "access-secret",
                        "aws_secret_access_key": "private-secret",
                    },
                },
                "runtime": {
                    "auto_instantiate": False,
                    "default_sql_output": "auto",
                    "default_csv_encoding": "utf-8",
                    "std_stream_max_bytes": 1000000,
                    "watcher_on_save": "lazy",
                    "reactive_tests": True,
                    "show_tracebacks": False,
                    "output_max_bytes": 8000000,
                    "auto_reload": "off",
                    "on_cell_change": "autorun",
                },
                "signing": {"private_key_path": "identity.key"},
            },
        }
    )


def test_invalid_user_file_snapshot(config_tree: Path) -> None:
    path = config_tree / "home" / ".marimo.toml"
    cases: dict[str, Any] = {}
    for name, content in [
        ("empty", ""),
        ("invalid", "[display\n"),
        ("unknown_keys", "[future]\nsetting = 42\n"),
    ]:
        path.write_text(content, encoding="utf-8")
        manager = get_default_config_manager(current_path=None)
        config = manager.get_user_config(hide_secrets=False)
        cases[name] = {
            "theme": config["display"]["theme"],
            "future": config.get("future"),
            "dotenv": config["runtime"].get("dotenv"),
        }
    assert cases == snapshot(
        {
            "empty": {"theme": "light", "future": None, "dotenv": None},
            "invalid": {"theme": "light", "future": None, "dotenv": None},
            "unknown_keys": {
                "theme": "light",
                "future": {"setting": 42},
                "dotenv": None,
            },
        }
    )


def test_dotenv_explicit_precedence_snapshot(config_tree: Path) -> None:
    """Explicit lists replace one another; empty project/script lists opt out."""
    project = config_tree / "home" / "project"
    user = config_tree / "home" / ".marimo.toml"
    pyproject = project / "pyproject.toml"
    notebook = project / "notebook.py"
    user.write_text('[runtime]\ndotenv = ["user.env"]\n', encoding="utf-8")
    cases: dict[str, Any] = {}
    for name, project_paths, script_paths, overrides in [
        ("user_only", None, None, None),
        (
            "project_replaces_user",
            '["first.env", "../shared.env"]',
            None,
            None,
        ),
        ("project_empty", "[]", None, None),
        ("script_replaces_project", '["project.env"]', '["script.env"]', None),
        ("script_empty", '["project.env"]', "[]", None),
        ("memory_empty", '["project.env"]', '["script.env"]', []),
        (
            "memory_replaces_script",
            '["project.env"]',
            '["script.env"]',
            ["memory.env"],
        ),
        (
            "absolute_path",
            f'["{(project / "absolute.env").as_posix()}"]',
            None,
            None,
        ),
    ]:
        pyproject.write_text(
            "[tool.marimo.runtime]\n"
            + (
                f"dotenv = {project_paths}\n"
                if project_paths is not None
                else ""
            ),
            encoding="utf-8",
        )
        write_script(
            notebook,
            "[tool.marimo.runtime]\n"
            + (
                f"dotenv = {script_paths}\n"
                if script_paths is not None
                else ""
            ),
        )
        manager = get_default_config_manager(current_path=str(notebook))
        if overrides is not None:
            manager = manager.with_overrides(
                cast("PartialMarimoConfig", {"runtime": {"dotenv": overrides}})
            )
        masked = manager.get_config()
        cases[name] = {
            "resolved": manager.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            ),
            "masked": masked["runtime"].get("dotenv"),
            "overrides": manager.get_config_overrides(hide_secrets=False).get(
                "runtime"
            ),
        }
    assert normalized(cases, config_tree) == snapshot(
        {
            "user_only": {
                "resolved": ["user.env"],
                "masked": [],
                "overrides": {},
            },
            "project_replaces_user": {
                "resolved": [
                    "<root>/home/project/first.env",
                    "<root>/home/project/../shared.env",
                ],
                "masked": [],
                "overrides": {
                    "dotenv": [
                        "<root>/home/project/first.env",
                        "<root>/home/project/../shared.env",
                    ]
                },
            },
            "project_empty": {
                "resolved": [],
                "masked": [],
                "overrides": {"dotenv": []},
            },
            "script_replaces_project": {
                "resolved": ["<root>/home/project/script.env"],
                "masked": [],
                "overrides": {"dotenv": ["<root>/home/project/script.env"]},
            },
            "script_empty": {
                "resolved": [],
                "masked": [],
                "overrides": {"dotenv": []},
            },
            "memory_empty": {
                "resolved": [],
                "masked": [],
                "overrides": {"dotenv": []},
            },
            "memory_replaces_script": {
                "resolved": ["memory.env"],
                "masked": [],
                "overrides": {"dotenv": ["memory.env"]},
            },
            "absolute_path": {
                "resolved": ["<root>/home/project/absolute.env"],
                "masked": [],
                "overrides": {"dotenv": ["<root>/home/project/absolute.env"]},
            },
        }
    )


def test_dotenv_workspace_session_snapshot(config_tree: Path) -> None:
    """Session readers anchor defaults without freezing masked path values."""
    project = config_tree / "home" / "project"
    nested = project / "notebooks"
    nested.mkdir()
    notebook = nested / "notebook.py"
    write_script(notebook, "")
    cases: dict[str, Any] = {}
    for name, anchor, script in [
        ("standalone_session", False, notebook),
        ("unsaved_session", False, None),
        ("project_session", True, notebook),
    ]:
        if anchor:
            (project / "pyproject.toml").write_text("", encoding="utf-8")
        manager = get_default_config_manager(current_path=str(project))
        session = manager.with_partial(
            ScriptConfigManager(str(script) if script is not None else None)
        )
        cases[name] = {
            "workspace": manager.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            ),
            "masked_session": session.get_config()["runtime"].get("dotenv"),
            "session": session.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            ),
            "overrides": session.get_config_overrides(hide_secrets=False),
        }
    assert normalized(cases, config_tree) == snapshot(
        {
            "standalone_session": {
                "workspace": ["<root>/home/project/.env"],
                "masked_session": [],
                "session": ["<root>/home/project/notebooks/.env"],
                "overrides": {},
            },
            "unsaved_session": {
                "workspace": ["<root>/home/project/.env"],
                "masked_session": [],
                "session": ["<root>/home/project/.env"],
                "overrides": {},
            },
            "project_session": {
                "workspace": ["<root>/home/project/.env"],
                "masked_session": [],
                "session": ["<root>/home/project/.env"],
                "overrides": {},
            },
        }
    )


def test_dotenv_home_and_nested_project_snapshot(
    config_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = config_tree / "home"
    project = home / "project"
    nested = project / "nested"
    nested.mkdir()
    notebook = nested / "notebook.py"
    write_script(notebook, "")
    cases: dict[str, Any] = {}

    def capture(name: str, path: Path) -> None:
        manager = get_default_config_manager(current_path=str(path))
        cases[name] = {
            "dotenv": manager.get_config(hide_secrets=False)["runtime"].get(
                "dotenv"
            ),
            "defaults": manager.get_config_defaults(hide_secrets=False),
        }

    capture("home_directory", home)
    home_notebook = home / "notebook.py"
    write_script(home_notebook, "")
    capture("home_notebook", home_notebook)
    write_script(
        home_notebook, '[tool.marimo.runtime]\ndotenv = ["explicit.env"]'
    )
    capture("home_explicit_script", home_notebook)
    (home / "pyproject.toml").write_text("", encoding="utf-8")
    capture("home_with_pyproject", home)
    (project / "pyproject.toml").write_text("", encoding="utf-8")
    capture("parent_project", notebook)
    (nested / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(home)
    capture("nearest_project_with_different_cwd", notebook)
    assert normalized(cases, config_tree) == snapshot(
        {
            "home_directory": {"dotenv": None, "defaults": {}},
            "home_notebook": {"dotenv": None, "defaults": {}},
            "home_explicit_script": {
                "dotenv": ["<root>/home/explicit.env"],
                "defaults": {},
            },
            "home_with_pyproject": {
                "dotenv": ["<root>/home/.env"],
                "defaults": {"runtime": {"dotenv": ["<root>/home/.env"]}},
            },
            "parent_project": {
                "dotenv": ["<root>/home/project/.env"],
                "defaults": {
                    "runtime": {"dotenv": ["<root>/home/project/.env"]}
                },
            },
            "nearest_project_with_different_cwd": {
                "dotenv": ["<root>/home/project/nested/.env"],
                "defaults": {
                    "runtime": {"dotenv": ["<root>/home/project/nested/.env"]}
                },
            },
        }
    )


@pytest.mark.usefixtures("config_tree")
def test_merge_semantics_snapshot() -> None:
    """Replace record maps and lists, but merge ordinary config sections."""
    from copy import deepcopy

    from marimo._config.config import merge_config, merge_default_config

    base = merge_default_config(
        cast(
            "PartialMarimoConfig",
            {
                "keymap": {"overrides": {"old": "Ctrl-A"}},
                "ai": {"custom_providers": {"old": {"api_key": "old"}}},
                "signing": {"trusted_signers": {"old": "old-key"}},
                "runtime": {"dotenv": ["old.env"], "auto_instantiate": True},
                "display": {"theme": "dark", "default_width": "full"},
            },
        )
    )
    original = deepcopy(base)
    cases: dict[str, Any] = {}
    for name, replacements in [
        ("new_records", True),
        ("empty_records", False),
    ]:
        patch = cast(
            "PartialMarimoConfig",
            {
                "keymap": {
                    "overrides": {"new": "Ctrl-B"} if replacements else {}
                },
                "ai": {
                    "custom_providers": {"new": {"api_key": "new"}}
                    if replacements
                    else {}
                },
                "signing": {
                    "trusted_signers": {"new": "new-key"}
                    if replacements
                    else {}
                },
                "runtime": {"dotenv": ["new.env"] if replacements else []},
                "display": {"theme": "light"},
            },
        )
        original_patch = deepcopy(patch)
        merged = merge_config(base, patch)
        assert base == original
        assert patch == original_patch
        cases[name] = {
            "keymap": merged["keymap"],
            "custom_providers": merged["ai"]["custom_providers"],
            "signing": merged["signing"],
            "dotenv": merged["runtime"].get("dotenv"),
            "auto_instantiate": merged["runtime"]["auto_instantiate"],
            "display": merged["display"],
        }
    for value in [False, True, "detect", "off", "lazy", "autorun"]:
        merged = merge_config(
            base,
            cast("PartialMarimoConfig", {"runtime": {"auto_reload": value}}),
        )
        cases[f"auto_reload_{value}"] = merged["runtime"]["auto_reload"]
    assert cases == snapshot(
        {
            "new_records": {
                "keymap": {
                    "overrides": {"new": "Ctrl-B"},
                    "preset": "default",
                },
                "custom_providers": {"new": {"api_key": "new"}},
                "signing": {"trusted_signers": {"new": "new-key"}},
                "dotenv": ["new.env"],
                "auto_instantiate": True,
                "display": {
                    "code_lens": True,
                    "code_editor_font_size": 14,
                    "cell_output": "below",
                    "dataframes": "rich",
                    "default_table_max_columns": 50,
                    "default_width": "full",
                    "reference_highlighting": True,
                    "default_table_page_size": 10,
                    "theme": "light",
                },
            },
            "empty_records": {
                "keymap": {"overrides": {}, "preset": "default"},
                "custom_providers": {},
                "signing": {"trusted_signers": {}},
                "dotenv": [],
                "auto_instantiate": True,
                "display": {
                    "code_lens": True,
                    "code_editor_font_size": 14,
                    "cell_output": "below",
                    "dataframes": "rich",
                    "default_table_max_columns": 50,
                    "default_width": "full",
                    "reference_highlighting": True,
                    "default_table_page_size": 10,
                    "theme": "light",
                },
            },
            "auto_reload_False": "off",
            "auto_reload_True": "lazy",
            "auto_reload_detect": "lazy",
            "auto_reload_off": "off",
            "auto_reload_lazy": "lazy",
            "auto_reload_autorun": "autorun",
        }
    )


def test_dotenv_loading_boundary_snapshot(
    config_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolution leaves the environment alone; loading honors existing vars."""
    from marimo._secrets.load_dotenv import load_dotenv_with_fallback

    project = config_tree / "home" / "project"
    prefix = "MARIMO_CONFIG_SNAPSHOT_"
    for key in ["EXISTING", "SHARED", "FIRST", "SECOND", "EXPANDED"]:
        # Register cleanup for keys created by the dotenv loader as well.
        monkeypatch.setenv(prefix + key, "")
        monkeypatch.delenv(prefix + key)
    monkeypatch.setenv(prefix + "EXISTING", "environment")
    (project / "first.env").write_text(
        f"{prefix}EXISTING=file\n{prefix}SHARED=first\n{prefix}FIRST=one\n",
        encoding="utf-8",
    )
    (project / "second.env").write_text(
        f"{prefix}SHARED=second\n{prefix}SECOND=two\n"
        f"{prefix}EXPANDED=${{{prefix}SHARED}}/${{{prefix}EXISTING}}\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.marimo.runtime]\ndotenv = ["first.env", "second.env"]\n',
        encoding="utf-8",
    )
    manager = get_default_config_manager(current_path=str(project))
    config = manager.get_config(hide_secrets=False)

    def environment() -> dict[str, str | None]:
        return {
            key: os.environ.get(prefix + key)
            for key in ["EXISTING", "SHARED", "FIRST", "SECOND", "EXPANDED"]
        }

    before = environment()
    for path in config["runtime"]["dotenv"]:
        load_dotenv_with_fallback(path)
    assert {
        "before_loading": before,
        "after_loading": environment(),
    } == snapshot(
        {
            "before_loading": {
                "EXISTING": "environment",
                "SHARED": None,
                "FIRST": None,
                "SECOND": None,
                "EXPANDED": None,
            },
            "after_loading": {
                "EXISTING": "environment",
                "SHARED": "first",
                "FIRST": "one",
                "SECOND": "two",
                "EXPANDED": "first/environment",
            },
        }
    )


def test_save_scope_and_refresh_snapshot(config_tree: Path) -> None:
    """Saving updates the user file without persisting higher-priority values."""
    home = config_tree / "home"
    project = home / "project"
    user = home / ".marimo.toml"
    pyproject = project / "pyproject.toml"
    notebook = project / "notebook.py"
    user.write_text('[display]\ntheme = "light"\n', encoding="utf-8")
    pyproject.write_text(
        '[tool.marimo.display]\ntheme = "dark"\n'
        '[tool.marimo.runtime]\ndotenv = ["project.env"]\n',
        encoding="utf-8",
    )
    write_script(notebook, "[tool.marimo.formatting]\nline_length = 100")
    original_project = pyproject.read_bytes()
    original_script = notebook.read_bytes()
    manager = get_default_config_manager(current_path=str(notebook))
    overridden = manager.with_overrides(
        cast("PartialMarimoConfig", {"formatting": {"line_length": 120}})
    )

    def capture() -> dict[str, Any]:
        resolved = manager.get_config(hide_secrets=False)
        user_config = manager.get_user_config(hide_secrets=False)
        return {
            "user_theme": user_config["display"]["theme"],
            "resolved_theme": resolved["display"]["theme"],
            "user_dotenv": user_config["runtime"].get("dotenv"),
            "resolved_dotenv": resolved["runtime"].get("dotenv"),
            "resolved_line_length": resolved["formatting"]["line_length"],
            "overridden_line_length": overridden.get_config(
                hide_secrets=False
            )["formatting"]["line_length"],
        }

    before = capture()
    manager.save_config(
        cast(
            "PartialMarimoConfig",
            {
                "display": {"theme": "system"},
                "runtime": {"dotenv": ["user.env"]},
            },
        )
    )
    after = capture()
    assert pyproject.read_bytes() == original_project
    assert notebook.read_bytes() == original_script
    assert normalized(
        {"before": before, "after": after}, config_tree
    ) == snapshot(
        {
            "before": {
                "user_theme": "light",
                "resolved_theme": "dark",
                "user_dotenv": None,
                "resolved_dotenv": ["<root>/home/project/project.env"],
                "resolved_line_length": 100,
                "overridden_line_length": 120,
            },
            "after": {
                "user_theme": "system",
                "resolved_theme": "dark",
                "user_dotenv": ["user.env"],
                "resolved_dotenv": ["<root>/home/project/project.env"],
                "resolved_line_length": 100,
                "overridden_line_length": 120,
            },
        }
    )
