# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class URLParamMapping:
    """Defines how a URL parameter maps to PEP 723 header configuration.

    Attributes:
        url_key: The key used in the URL (e.g., "venv")
        config_path: Tuple of keys for nested TOML path
            (e.g., ("tool", "marimo", "env", "venv"))
        description: Human-readable description for documentation
    """

    url_key: str
    config_path: tuple[str, ...]
    description: str = ""


# The lookup table for URL params that map to PEP 723 header config.
# Adding new params is as simple as adding an entry here.
URL_PARAM_MAPPINGS: dict[str, URLParamMapping] = {
    "venv": URLParamMapping(
        url_key="venv",
        config_path=("tool", "marimo", "env", "venv"),
        description="Virtual environment path for the notebook",
    ),
    # Add more mappings here as needed, e.g.:
    # "theme": URLParamMapping(
    #     url_key="theme",
    #     config_path=("tool", "marimo", "display", "theme"),
    #     description="Display theme (light, dark, system)",
    # ),
}

# Keys that should be filtered from user-facing query params
# (these are marimo internal params, not passed to mo.query_params())
INTERNAL_URL_PARAM_KEYS = frozenset(URL_PARAM_MAPPINGS.keys())


def build_header_from_params(params: dict[str, str]) -> str | None:
    """Build PEP 723 header string from URL params.

    Args:
        params: Dictionary of URL parameter key-value pairs

    Returns:
        PEP 723 formatted header string, or None if no matching params
    """
    from marimo._utils.scripts import write_pyproject_to_script

    config: dict[str, Any] = {}
    for key, value in params.items():
        if key not in URL_PARAM_MAPPINGS:
            continue

        mapping = URL_PARAM_MAPPINGS[key]
        # Build nested dict from path
        d: dict[str, Any] = config
        for part in mapping.config_path[:-1]:
            d = d.setdefault(part, {})
        d[mapping.config_path[-1]] = value

    if not config:
        return None

    return write_pyproject_to_script(config)
