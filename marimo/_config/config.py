# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, TypedDict, cast

from marimo._utils.deep_merge import deep_merge

if TYPE_CHECKING:
    from typing import Literal, Optional


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


class SaveConfig(TypedDict, total=False):
    """Configuration for saving.

    **Keys.**

    - `autosave`: one of `"off"` or `"after_delay"`
    - `delay`: number of milliseconds to wait before autosaving
    - `format_on_save`: if `True`, format the code on save
    """

    autosave: Literal["off", "after_delay"]
    autosave_delay: int
    format_on_save: bool


class KeymapConfig(TypedDict, total=False):
    """Configuration for keymaps.

    **Keys.**

    - `preset`: one of `"default"` or `"vim"`
    """

    preset: Literal["default", "vim"]


# Byte limits on outputs exist for two reasons:
#
# 1. We use a multiprocessing.Connection object to send outputs from
#    the kernel to the server (the server then sends the output to
#    the frontend via a websocket). The Connection object has a limit
#    of ~32MiB that it can send before it chokes
#    (https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection.send).
#
#    TODO(akshayka): Get around this by breaking up the message sent
#    over the Connection or plumbing the websocket into the kernel.
#
# 2. The frontend chokes when we send outputs that are too big, i.e.
#    it freezes and sometimes even crashes. That can lead to lost work.
#    It appears this is the bottleneck right now, compared to 1.
#
# Usually users only output gigantic things accidentally, so refusing
# to show large outputs should in most cases not bother the user too much.
# In any case, it's better than breaking the frontend/kernel.
class RuntimeConfig(TypedDict, total=False):
    """Configuration for runtime.

    **Keys.**

    - `auto_instantiate`: if `False`, cells won't automatically
        run on startup. This only applies when editing a notebook,
        and not when running as an application. The default is `True`.
    - `output_max_size_bytes`: max size in bytes for cell outputs; increasing
         this lets you render larger outputs, but may lead to performance
         issues
    - `std_stream_max_size_bytes`: max size in MB for stdout/stderr messages;
        increasing this lets you render larger messages, but may lead to
        performance issues
    """

    auto_instantiate: bool
    output_max_size_bytes: int
    std_stream_max_size_bytes: int


class DisplayConfig(TypedDict, total=False):
    """Configuration for display.

    **Keys.**

    - `theme`: `"light"` or `"dark"`
    """

    theme: Literal["light", "dark"]


class ServerConfig(TypedDict, total=False):
    """Configuration for the server.

    **Keys.**

    - `browser`: the web browser to use. `"default"` or a browser registered
        with Python's webbrowser module (eg, `"firefox"` or `"chrome"`)
    """

    browser: Literal["default"] | str


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
    """

    completion: CompletionConfig
    display: DisplayConfig
    keymap: KeymapConfig
    runtime: RuntimeConfig
    save: SaveConfig
    server: ServerConfig
    experimental: Dict[str, Any]


OUTPUT_MAX_SIZE_BYTES = 5_000_000
STD_STREAM_MAX_SIZE_BYTES = 1_000_000

DEFAULT_CONFIG: MarimoConfig = {
    "completion": {"activate_on_typing": True, "copilot": False},
    "display": {"theme": "light"},
    "keymap": {"preset": "default"},
    "runtime": {
        "auto_instantiate": True,
        "output_max_size_bytes": OUTPUT_MAX_SIZE_BYTES,
        "std_stream_max_size_bytes": STD_STREAM_MAX_SIZE_BYTES,
    },
    "save": {
        "autosave": "after_delay",
        "autosave_delay": 1000,
        "format_on_save": False,
    },
    "server": {"browser": "default"},
}
_USER_CONFIG: Optional[MarimoConfig] = None


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
