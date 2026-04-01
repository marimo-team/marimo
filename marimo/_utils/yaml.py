# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any, Callable, TypeAlias

import yaml
from yaml.representer import SafeRepresenter, ScalarNode

# Regex captures loose yaml for frontmatter
# Should match the following:
# ---
# title: "Title"
# whatever
# ---
YAML_FRONT_MATTER_REGEX = re.compile(
    r"^---\s*\n(.*?\n?)(?:---)\s*\n", re.UNICODE | re.DOTALL
)

Repr: TypeAlias = Callable[[SafeRepresenter, str], ScalarNode]


# represent_str does handle some corner cases, so use that
# instead of calling represent_scalar directly
class folded_str(str):
    """A str subclass that is serialized with YAML folded (>) block style."""


class literal_str(str):
    """A str subclass that is serialized with YAML literal (|) block style."""


def _format_header_value(k: str, v: Any) -> Any:
    if not isinstance(v, str):
        return v
    if k in ("pyproject", "header") or "\n" in v:
        return literal_str(v)
    if k == "description":
        return folded_str(v)
    return v


def dump(data: dict[str, Any], **kwargs: Any) -> str:
    """Serialize a dict to a YAML string, respecting folded_str and literal_str block styles."""

    def _change_style(style: str, representer: Repr) -> Repr:
        def new_representer(dumper: SafeRepresenter, data: str) -> ScalarNode:
            scalar = representer(dumper, data)
            scalar.style = style
            return scalar

        return new_representer

    represent_folded_str = _change_style(">", SafeRepresenter.represent_str)
    represent_literal_str = _change_style("|", SafeRepresenter.represent_str)
    yaml.add_representer(folded_str, represent_folded_str)
    yaml.add_representer(literal_str, represent_literal_str)

    response = yaml.dump(data, **kwargs)
    assert isinstance(response, str), f"Expected str, got {type(response)}"
    return response


def marimo_compat_dump(data: dict[str, Any], **kwargs: Any) -> str:
    """Serialize a marimo frontmatter dict to YAML, applying appropriate block styles per key."""
    safe_data = {k: _format_header_value(k, v) for k, v in data.items()}
    return dump(safe_data, **kwargs)


def load(yaml_content: str) -> dict[str, Any]:
    """Parse a YAML string and return it as a dict using the fastest available safe loader."""
    # CSafeLoader is faster than SafeLoader.
    try:
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import SafeLoader  # type: ignore[assignment]
    response = yaml.load(yaml_content, SafeLoader)
    assert isinstance(response, dict), f"Expected dict, got {type(response)}"
    return response


YAMLError = yaml.YAMLError
