# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any, Optional, TypeVar, cast

from typing_extensions import Literal

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

from marimo._output.rich_help import mddoc


@mddoc
class CompletionConfig(TypedDict, total=False):
    """Configuration for code completion.

    A dict with key/value pairs configuring code completion in the marimo
    editor.

    **Keys.**

    - `activate_on_typing`: if `False`, completion won't activate
    until the completion hotkey is entered
    """

    activate_on_typing: bool


@mddoc
class SaveConfig(TypedDict, total=False):
    """Configuration for saving.

    **Keys.**

    - `autosave`: one of `"off"` or `"after_delay"`
    - `delay`: number of milliseconds to wait before autosaving
    """

    autosave: Literal["off", "after_delay"]
    autosave_delay: int


@mddoc
class MarimoConfig(TypedDict, total=False):
    """Configuration for the marimo editor.

    A marimo configuration is a Python `dict`. Configurations
    can be partially specified, with just a subset of possible keys.
    Partial configs will be augmented with default options.

    Use with `configure` to configure the editor. See `configure`
    documentation for details on how to register the configuration.

    **Example.**

    ```python3
    config: mo.config.MarimoConfig = {
        "completion": {"activate_on_typing": True},
    }
    ```

    **Keys.**

    - `completion`: a `CompletionConfig`
    - `save`: a `SaveConfig`
    """

    completion: CompletionConfig
    save: SaveConfig


_DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True},
    "save": {"autosave": "off", "autosave_delay": 1000},
}
_USER_CONFIG: Optional[MarimoConfig] = None

ConfigType = TypeVar("ConfigType", MarimoConfig, SaveConfig, CompletionConfig)


# TODO(akshayka): Type-safety, can't index into TypedDict with nonliteral
def _merge_key(defaults: Any, override: Any, key: str, path: list[str]) -> Any:
    if key not in defaults:
        pathstr = " (" + ".".join(path + [key]) + ")" if path else ""
        raise TypeError("Invalid setting in MarimoConfig: " + key + pathstr)
    elif key not in override:
        return defaults[key]
    elif not isinstance(defaults[key], dict):
        return override[key]
    else:
        return _merge_configs(defaults[key], override[key], path=path + [key])


def _merge_configs(
    defaults: ConfigType, override: ConfigType, path: list[str]
) -> ConfigType:
    return cast(
        ConfigType,
        {
            key: _merge_key(defaults, override, key, path)
            for key in set(defaults.keys()).union(set(override.keys()))
        },
    )


@mddoc
def configure(config: MarimoConfig) -> None:
    """Configure the marimo editor.

    Place a call to this function in a file named `marimo.config.py`, and
    marimo will use `config` to configure the editor.

    marimo searches for a config file from the directory in which it was
    started back to the home directory, using the first file it finds.

    **Example.**

    To have autosave enabled and code completion activate automatically as you
    type, create a file named `marimo.config.py` in your home directory and
    paste the following code into it.

    ```python3
    import marimo as mo


    mo.config.configure(
        config={
            # Automatically activate completions
            "completion": {"activate_on_typing": True},
            # Autosave after a delay of 1000ms
            "save": {"autosave": "after_delay", "autosave_delay": 1000},
        }
    )
    ```

    **Args.**

    - `config`: A configuration object.
    """
    global _USER_CONFIG
    _USER_CONFIG = _merge_configs(_DEFAULT_CONFIG, config, [])


def get_configuration() -> MarimoConfig:
    """Return the current configuration."""
    return _USER_CONFIG if _USER_CONFIG is not None else _DEFAULT_CONFIG
