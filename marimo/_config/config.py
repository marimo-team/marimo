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
class KeymapConfig(TypedDict, total=False):
    """Configuration for keymaps.

    **Keys.**

    - `preset`: one of `"default"` or `"vim"`
    """

    preset: Literal["default", "vim"]


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
    - `keymap`: a `KeymapConfig`
    """

    completion: CompletionConfig
    save: SaveConfig
    keymap: KeymapConfig


DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True},
    "save": {"autosave": "after_delay", "autosave_delay": 1000},
    "keymap": {"preset": "default"},
}
_USER_CONFIG: Optional[MarimoConfig] = None

ConfigType = TypeVar(
    "ConfigType", MarimoConfig, SaveConfig, CompletionConfig, KeymapConfig
)


# TODO(akshayka): Type-safety, can't index into TypedDict with nonliteral
def _merge_key(defaults: Any, override: Any, key: str) -> Any:
    if key not in defaults:
        # forward compatibility: old versions of marimo won't be aware of new
        # settings. Config might also have misspelled keys, but shouldn't fail
        # if that happens.
        return override[key]
    elif key not in override:
        return defaults[key]
    elif not isinstance(defaults[key], dict):
        return override[key]
    else:
        return _merge_configs(defaults[key], override[key])


def _merge_configs(defaults: ConfigType, override: ConfigType) -> ConfigType:
    return cast(
        ConfigType,
        {
            key: _merge_key(defaults, override, key)
            for key in set(defaults.keys()).union(set(override.keys()))
        },
    )


@mddoc
def configure(config: MarimoConfig) -> MarimoConfig:
    """Configure the marimo editor with a user config.

    **Args.**

    - `config`: A configuration object.
    """
    global _USER_CONFIG
    # Robust merging of configs (want to merge on leaves, not just keys)
    _USER_CONFIG = cast(MarimoConfig, _merge_configs(DEFAULT_CONFIG, config))
    return _USER_CONFIG


def get_configuration() -> MarimoConfig:
    """Return the current configuration."""
    return cast(
        MarimoConfig,
        _USER_CONFIG if _USER_CONFIG is not None else DEFAULT_CONFIG,
    )
