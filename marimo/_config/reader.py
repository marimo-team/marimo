# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from marimo import _loggers
from marimo._config.config import PartialMarimoConfig
from marimo._utils.toml import toml_reader

LOGGER = _loggers.marimo_logger()


def read_marimo_config(path: str) -> PartialMarimoConfig:
    """Read the marimo.toml configuration."""
    return cast(PartialMarimoConfig, toml_reader.read(path))


def read_pyproject_marimo_config(
    pyproject_path: str | Path,
) -> PartialMarimoConfig | None:
    """Read the marimo tool config from a pyproject.toml file."""
    pyproject_config = toml_reader.read(pyproject_path)
    marimo_tool_config = get_marimo_config_from_pyproject_dict(
        pyproject_config
    )
    if marimo_tool_config is None:
        return None
    LOGGER.info("Found marimo config in pyproject.toml at %s", pyproject_path)
    return marimo_tool_config


def _pop_nested_key(root: dict[str, Any], key_path: tuple[str, ...]) -> bool:
    """Delete `root[key_path...]` if present. Returns whether it was deleted."""
    current = root
    for key in key_path[:-1]:
        nxt = current.get(key)
        if not isinstance(nxt, dict):
            return False
        current = nxt
    if key_path[-1] in current:
        del current[key_path[-1]]
        return True
    return False


def sanitize_pyproject_dict(
    pyproject_dict: dict[str, Any], keys: tuple[tuple[str, ...], ...]
) -> dict[str, Any]:
    """Sanitize the pyproject.toml dictionary by removing specified keys."""
    for key_path in keys:
        # NB. each key_path is independent — a missing parent skips that path
        # rather than aborting the rest.
        if _pop_nested_key(pyproject_dict, key_path):
            LOGGER.warning(
                "%s in script metadata is ignored for security reasons",
                ".".join(key_path),
            )
    return pyproject_dict


# Top-level `tool.marimo` sections that notebook (PEP 723) inline metadata is
# permitted to set. Notebook metadata is attacker-controllable and merged with
# the HIGHEST precedence over the operator's own user config, so anything that
# affects outbound traffic or credentials must stay excluded: `ai` (base_url
# → credential exfiltration), `mcp` (url → outbound beacon), `completion`
# (api_key/base_url), `secrets`, `server`.
#
# NB. `runtime.auto_instantiate`, `experimental.isolate_apps`, and
# `display.custom_css` are additionally stripped even though their parent
# sections are allowed — forcing `auto_instantiate`/`isolate_apps` changes
# what happens to the operator with no explicit "run" action, and
# `custom_css` points to files that are read and inlined into the served
# HTML before cell execution.
ALLOWED_SCRIPT_CONFIG_TOP_KEYS: frozenset[str] = frozenset(
    {
        "formatting",
        "save",
        "display",
        "keymap",
        "diagnostics",
        "lint",
        "snippets",
        "datasources",
        "language_servers",
        "sharing",
        "venv",
        "runtime",
        "experimental",
        "package_management",
    }
)


def _get_tool_dict(pyproject_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract marimo tool definition."""
    tool = pyproject_dict.get("tool", {})
    # NB tool _should_ be a table from pyproject standard.
    if not isinstance(tool, dict):
        raise ValueError(
            f"pyproject.toml/script metadata 'tool' must be a table, "
            f"got {type(tool).__name__}"
        )
    return tool


def allowlist_script_config(
    pyproject_dict: dict[str, Any], allowed_top: frozenset[str]
) -> dict[str, Any]:
    """Drop every `tool.marimo.<key>` section not in `allowed_top`."""
    marimo = _get_tool_dict(pyproject_dict).get("marimo", None)
    if not isinstance(marimo, dict):
        return pyproject_dict
    for key in list(marimo.keys()):
        if key not in allowed_top:
            LOGGER.warning(
                "tool.marimo.%s in script metadata is ignored for security reasons",
                key,
            )
            del marimo[key]
    return pyproject_dict


# Settings that an untrusted-origin config layer must not set. Both take effect
# before any cell runs, so a layer that sets one decides something the operator
# never agreed to:
#
#   signing              trusting a key is a code-execution grant, because a
#                        cache restore is `pickle.loads`
#   cache.verification   whether signatures are checked at all
#
# Both are anchored only in trusted user/environment config.
_UNTRUSTED_MARIMO_KEYS: tuple[tuple[str, ...], ...] = (
    ("signing",),
    ("cache", "verification"),
)

# `cache.store` is not a trust anchor on its own: the verifying loaders check
# the bytes it returns before unpickling, and the unsigned `PickleLoader`
# refuses a store it can identify as untrusted. That identification works by
# looking for the store in the config *overrides*, which covers the project and
# script layers. A workspace `.marimo.toml` loads as the user layer instead, so
# it never appears there — the loader cannot tell it apart from a store the
# operator chose. Strip it for that layer rather than leave an unidentifiable
# store behind.
_UNTRUSTED_USER_LAYER_KEYS: tuple[tuple[str, ...], ...] = (
    *_UNTRUSTED_MARIMO_KEYS,
    ("cache", "store"),
)


def strip_untrusted_config(
    config: PartialMarimoConfig, *, is_user_layer: bool = False
) -> PartialMarimoConfig:
    """Drop security-sensitive settings from an untrusted config layer.

    Mutates and returns `config`. A cloned repo's `pyproject.toml`, a shared
    notebook's PEP 723 header, and a workspace-discovered `.marimo.toml` are all
    untrusted origin: cloning a repo or opening a notebook is not consent to
    that repo's author choosing whose signed cache you unpickle.

    Set `is_user_layer` for the workspace `.marimo.toml`, which additionally
    loses `cache.store`.
    """
    keys = (
        _UNTRUSTED_USER_LAYER_KEYS if is_user_layer else _UNTRUSTED_MARIMO_KEYS
    )
    sanitized = cast(dict[str, Any], config)
    for key_path in keys:
        if _pop_nested_key(sanitized, key_path):
            LOGGER.warning(
                "Ignored %s from a configuration file that travels with the "
                "code. Set it in your user configuration instead.",
                ".".join(key_path),
            )
    return config


def get_marimo_config_from_pyproject_dict(
    pyproject_dict: dict[str, Any],
) -> PartialMarimoConfig | None:
    """Get the marimo config from a pyproject.toml dictionary."""
    marimo_tool_config = _get_tool_dict(pyproject_dict).get("marimo", None)
    if marimo_tool_config is None:
        return None
    if not isinstance(marimo_tool_config, dict):
        LOGGER.warning(
            "pyproject.toml contains invalid marimo config: %s",
            marimo_tool_config,
        )
        return None
    return cast(PartialMarimoConfig, marimo_tool_config)


def find_nearest_pyproject_toml(
    start_path: str | Path,
) -> Path | None:
    """Find the nearest pyproject.toml file."""
    path = Path(start_path)
    root = path.anchor
    try:
        while not path.joinpath("pyproject.toml").exists():
            if str(path) == root:
                return None
            if path.parent == path:
                return None
            path = path.parent
    except OSError:
        return None
    return path.joinpath("pyproject.toml")
