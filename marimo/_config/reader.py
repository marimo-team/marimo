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


def sanitize_pyproject_dict(
    pyproject_dict: dict[str, Any], keys: tuple[tuple[str, ...], ...]
) -> dict[str, Any]:
    """Sanitize the pyproject.toml dictionary by removing specified keys."""
    for key_path in keys:
        current_level = pyproject_dict
        missing_intermediate = False
        for key in key_path[:-1]:
            if key in current_level and isinstance(current_level[key], dict):
                current_level = current_level[key]
            else:
                missing_intermediate = True
                break
        if missing_intermediate:
            continue
        if current_level and key_path[-1] in current_level:
            LOGGER.warning(
                "%s in script metadata is ignored for security reasons",
                ".".join(key_path),
            )
            del current_level[key_path[-1]]
    return pyproject_dict


# Top-level `tool.marimo` sections that notebook (PEP 723) inline metadata is
# permitted to set. Notebook metadata is attacker-controllable and merged with
# the HIGHEST precedence over the operator's own user config, so anything that
# affects outbound traffic or credentials must stay excluded: `ai` (base_url
# → credential exfiltration), `mcp` (url → outbound beacon), `completion`
# (api_key/base_url), `secrets`, `server`.
#
# NB. `runtime.auto_instantiate` and `experimental.isolate_apps` are
# additionally stripped even though their parent sections are allowed —
# forcing either one changes what happens to the operator with no explicit
# "run" action.
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
