# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

from typing import Any, Dict, Literal, TypedDict, Union, cast

from marimo._output.rich_help import mddoc
from marimo._utils.deep_merge import deep_merge


@mddoc
class CompletionConfig(TypedDict):
    """Configuration for code completion.

    A dict with key/value pairs configuring code completion in the marimo
    editor.

    **Keys.**

    - `activate_on_typing`: if `False`, completion won't activate
    until the completion hotkey is entered
    - `copilot`: if `True`, enable the GitHub Copilot language server
    """

    activate_on_typing: bool
    copilot: bool


@mddoc
class SaveConfig(TypedDict):
    """Configuration for saving.

    **Keys.**

    - `autosave`: one of `"off"` or `"after_delay"`
    - `delay`: number of milliseconds to wait before autosaving
    - `format_on_save`: if `True`, format the code on save
    """

    autosave: Literal["off", "after_delay"]
    autosave_delay: int
    format_on_save: bool


@mddoc
class KeymapConfig(TypedDict, total=False):
    """Configuration for keymaps.

    **Keys.**

    - `preset`: one of `"default"` or `"vim"`
    """

    preset: Literal["default", "vim"]


@mddoc
class RuntimeConfig(TypedDict):
    """Configuration for runtime.

    **Keys.**

    - `auto_instantiate`: if `False`, cells won't automatically
        run on startup. This only applies when editing a notebook,
        and not when running as an application.
        The default is `True`.
    - `auto_reload`: if `True`, modified modules will be automatically reloaded
       before cell execution; similar to IPython's %autoreload 2.
    """

    auto_instantiate: bool
    auto_reload: bool


@mddoc
class DisplayConfig(TypedDict):
    """Configuration for display.

    **Keys.**

    - `theme`: `"light"`, `"dark"`, or `"system"`
    - `code_editor_font_size`: font size for the code editor
    - `cell_output`: `"above"` or `"below"`
    """

    theme: Literal["light", "dark", "system"]
    code_editor_font_size: int
    cell_output: Literal["above", "below"]


@mddoc
class FormattingConfig(TypedDict):
    """Configuration for code formatting.

    **Keys.**

    - `line_length`: max line length
    """

    line_length: int


class ServerConfig(TypedDict):
    """Configuration for the server.

    **Keys.**

    - `browser`: the web browser to use. `"default"` or a browser registered
        with Python's webbrowser module (eg, `"firefox"` or `"chrome"`)
    """

    browser: Union[Literal["default"], str]


class PackageManagementConfig(TypedDict):
    """Configuration options for package management.

    **Keys.**

    - `manager`: the package manager to use
    """

    manager: Literal["pip", "rye", "uv", "poetry", "pixi"]


class AiConfig(TypedDict):
    """Configuration options for AI.

    **Keys.**

    - `open_ai`: the OpenAI config
    """

    open_ai: OpenAiConfig


class OpenAiConfig(TypedDict):
    """Configuration options for OpenAI or OpenAI-compatible services.

    **Keys.**

    - `api_key`: the OpenAI API key
    - `model`: the model to use
    - `base_url`: the base URL for the API
    """

    api_key: str
    model: NotRequired[str]
    base_url: NotRequired[str]


@mddoc
class MarimoConfig(TypedDict):
    """Configuration for the marimo editor"""

    completion: CompletionConfig
    display: DisplayConfig
    formatting: FormattingConfig
    keymap: KeymapConfig
    runtime: RuntimeConfig
    save: SaveConfig
    server: ServerConfig
    package_management: PackageManagementConfig
    ai: NotRequired[AiConfig]
    experimental: NotRequired[Dict[str, Any]]


DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True, "copilot": False},
    "display": {
        "theme": "light",
        "code_editor_font_size": 14,
        "cell_output": "above",
    },
    "formatting": {"line_length": 79},
    "keymap": {"preset": "default"},
    "runtime": {"auto_instantiate": True, "auto_reload": False},
    "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": False,
    },
    "package_management": {"manager": "pip"},
    "server": {"browser": "default"},
}


def merge_default_config(config: MarimoConfig) -> MarimoConfig:
    """Merge a user configuration with the default configuration."""
    return merge_config(DEFAULT_CONFIG, config)


def merge_config(
    config: MarimoConfig, new_config: MarimoConfig
) -> MarimoConfig:
    """Merge a user configuration with a new configuration."""
    return cast(
        MarimoConfig,
        deep_merge(
            cast(Dict[Any, Any], config), cast(Dict[Any, Any], new_config)
        ),
    )


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}  # type: ignore
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]  # type: ignore
    return obj


SECRET_PLACEHOLDER = "********"


def mask_secrets(config: MarimoConfig) -> MarimoConfig:
    def deep_remove_from_path(path: list[str], obj: Dict[str, Any]) -> None:
        key = path[0]
        if key not in obj:
            return
        if len(path) == 1:
            if obj[key]:
                obj[key] = SECRET_PLACEHOLDER
        else:
            deep_remove_from_path(path[1:], cast(Dict[str, Any], obj[key]))

    secrets = [["ai", "open_ai", "api_key"]]

    new_config = _deep_copy(config)
    for secret in secrets:
        deep_remove_from_path(secret, cast(Dict[str, Any], new_config))

    return new_config  # type: ignore


def remove_secret_placeholders(config: MarimoConfig) -> MarimoConfig:
    def deep_remove(obj: Any) -> Any:
        if isinstance(obj, dict):
            # Filter all keys with value SECRET_PLACEHOLDER
            return {
                k: deep_remove(v)
                for k, v in obj.items()
                if v != SECRET_PLACEHOLDER
            }  # type: ignore
        if isinstance(obj, list):
            return [deep_remove(v) for v in obj]  # type: ignore
        if obj == SECRET_PLACEHOLDER:
            return None
        return obj

    return deep_remove(_deep_copy(config))  # type: ignore
