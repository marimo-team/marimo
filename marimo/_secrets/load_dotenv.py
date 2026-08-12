# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import re

from marimo._dependencies.dependencies import DependencyManager


def load_dotenv_with_fallback(file: str) -> None:
    """Load a .env file using the dotenv library, falling to our custom
    implementation if the dotenv library is not installed.
    """
    if DependencyManager.dotenv.has():
        from dotenv import load_dotenv

        # By default, load_dotenv does not override existing keys in the
        # environment.
        load_dotenv(file)
    else:
        load_to_environ(parse_dotenv(file))


def read_dotenv_with_fallback(file: str) -> dict[str, str | None]:
    """Read a .env file using the dotenv library, falling to our custom
    implementation if the dotenv library is not installed.
    """
    if DependencyManager.dotenv.has():
        from dotenv import dotenv_values

        return dotenv_values(file)
    else:
        return parse_dotenv(file)


def parse_dotenv(filepath: str) -> dict[str, str | None]:
    """Parse a .env file into a dictionary of key-value pairs."""
    env_dict: dict[str, str | None] = {}
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
                env_dict[key] = value
    except FileNotFoundError:
        # Handle case where .env file doesn't exist
        pass
    return env_dict


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
