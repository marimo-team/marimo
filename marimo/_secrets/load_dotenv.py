# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
from functools import partial
from typing import TYPE_CHECKING

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


_POSIX_VARIABLE = re.compile(
    r"\$\{(?P<name>[^}:]*)(?::-(?P<default>[^}]*))?\}"
)


def load_dotenv_with_fallback(file: str) -> None:
    """Load a .env file using the dotenv library, falling to our custom
    implementation if the dotenv library is not installed.
    """
    load_to_environ(read_dotenv_with_fallback(file, environment=os.environ))


def read_dotenv_with_fallback(
    file: str,
    *,
    environment: Mapping[str, str | None] | None = None,
) -> dict[str, str | None]:
    """Read a .env file using the dotenv library, falling to our custom
    implementation if the dotenv library is not installed.
    """
    environment_overrides = environment is not None
    return _interpolate_dotenv_values(
        _read_dotenv_bindings(file),
        os.environ if environment is None else environment,
        environment_overrides=environment_overrides,
    )


def resolve_dotenv_value(
    key: str,
    files: Sequence[str],
    environment: Mapping[str, str],
) -> str | None:
    """Resolve one value using environment and dotenv file precedence."""
    resolved = dict(environment)
    if key in resolved:
        return resolved[key]

    for file in files:
        file_values = read_dotenv_with_fallback(file, environment=resolved)
        for name, value in file_values.items():
            if name not in resolved and value is not None:
                resolved[name] = value
        if key in resolved:
            return resolved[key]

    return None


def _interpolate_dotenv_values(
    values: Iterable[tuple[str, str | None]],
    environment: Mapping[str, str | None],
    *,
    environment_overrides: bool,
) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for key, value in values:
        if value is None:
            resolved[key] = None
            continue

        if environment_overrides:
            # Match `load_dotenv(..., override=False)` when resolving a chain.
            interpolation_environment = {**resolved, **environment}
        else:
            # Preserve `dotenv_values` behavior for existing callers.
            interpolation_environment = {**environment, **resolved}
        resolved[key] = _POSIX_VARIABLE.sub(
            partial(_resolve_variable, environment=interpolation_environment),
            value,
        )
    return resolved


def _resolve_variable(
    match: re.Match[str], environment: Mapping[str, str | None]
) -> str:
    default = match.group("default") or ""
    value = environment.get(match.group("name"), default)
    return "" if value is None else value


def _read_dotenv_bindings(file: str) -> list[tuple[str, str | None]]:
    """Read bindings in source order, including duplicate assignments."""
    if not DependencyManager.dotenv.has():
        return list(_parse_dotenv_bindings(file))

    from dotenv.parser import parse_stream

    try:
        with open(file, encoding="utf-8") as stream:
            return [
                (binding.key, binding.value)
                for binding in parse_stream(stream)
                if binding.key is not None and not binding.error
            ]
    except FileNotFoundError:
        return []


def parse_dotenv(filepath: str) -> dict[str, str | None]:
    """Parse a .env file into a dictionary of key-value pairs."""
    return dict(_parse_dotenv_bindings(filepath))


def _parse_dotenv_bindings(
    filepath: str,
) -> Iterable[tuple[str, str | None]]:
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Handle lines without equals sign
                if "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue

                value = _drop_quotes(value.strip())
                yield key, value
    except FileNotFoundError:
        # Handle case where .env file doesn't exist
        return


def load_to_environ(env_dict: dict[str, str | None]) -> None:
    """Load a dictionary of key-value pairs into the environment."""
    for key, value in env_dict.items():
        if key in os.environ:
            # By default, load_dotenv does not override existing keys in the
            # environment, so we should do the same.
            continue
        if value is None:
            continue
        os.environ[key] = value


# The escape sequences that python-dotenv decodes inside double-quoted
# values; we mirror them so both parsers agree on what a value means.
_ESCAPES = {
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
_ESCAPE_SEQUENCE = re.compile(r"\\([\\'\"abfnrtv])")


def escape_dotenv_value(value: str) -> str:
    """Escape a value so it can be written as a double-quoted .env value.

    The inverse of the unescaping done by `_drop_quotes` (and by
    python-dotenv). Newlines are escaped as well, since a raw newline would
    otherwise split the value across lines.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def _drop_quotes(value: str) -> str:
    # Handle quoted values (both single and double quotes)
    if len(value) < 2:
        return value
    if value.startswith("'") and value.endswith("'"):
        # Single-quoted values are taken literally.
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        # Double-quoted values may contain escape sequences.
        return _ESCAPE_SEQUENCE.sub(
            lambda match: _ESCAPES[match.group(1)], value[1:-1]
        )

    return value
