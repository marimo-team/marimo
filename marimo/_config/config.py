# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any, Dict, Optional, cast

from typing_extensions import Literal

if sys.version_info < (3, 8):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

from marimo._output.rich_help import mddoc
from marimo._utils.deep_merge import deep_merge


@mddoc
class CompletionConfig(TypedDict, total=False):
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
class RuntimeConfig(TypedDict, total=False):
    """Configuration for runtime.

    **Keys.**

    - `auto_instantiate`: if `False`, cells won't automatically
        run on startup. This only applies when editing a notebook,
        and not when running as an application.
        The default is `True`.
    """

    auto_instantiate: bool


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
    - `experimental`: a `dict` of experimental features
    """

    completion: CompletionConfig
    save: SaveConfig
    keymap: KeymapConfig
    runtime: RuntimeConfig
    experimental: Dict[str, Any]


DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True, "copilot": False},
    "save": {"autosave": "after_delay", "autosave_delay": 1000},
    "keymap": {"preset": "default"},
    "runtime": {"auto_instantiate": True},
}
_USER_CONFIG: Optional[MarimoConfig] = None


@mddoc
def configure(config: MarimoConfig) -> MarimoConfig:
    """Configure the marimo editor with a user config.

    **Args.**

    - `config`: A configuration object.
    """
    global _USER_CONFIG
    _USER_CONFIG = cast(
        MarimoConfig,
        deep_merge(
            cast(Dict[Any, Any], DEFAULT_CONFIG), cast(Dict[Any, Any], config)
        ),
    )
    return _USER_CONFIG


def get_configuration() -> MarimoConfig:
    """Return the current configuration."""
    return cast(
        MarimoConfig,
        _USER_CONFIG if _USER_CONFIG is not None else DEFAULT_CONFIG,
    )
