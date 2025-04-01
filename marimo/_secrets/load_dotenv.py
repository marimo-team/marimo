from __future__ import annotations

import os

from marimo._dependencies.dependencies import DependencyManager


def load_dotenv_with_fallback(file: str) -> None:
    """Load a .env file using the dotenv library, falling to our custom
    implementation if the dotenv library is not installed.
    """
    if DependencyManager.dotenv.has():
        from dotenv import load_dotenv  # type: ignore[import-not-found]

        load_dotenv(file)
    else:
        load_to_environ(parse_dotenv(file))


def parse_dotenv(filepath: str) -> dict[str, str]:
    """Parse a .env file into a dictionary of key-value pairs."""
    env_dict: dict[str, str] = {}
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


def load_to_environ(env_dict: dict[str, str]) -> None:
    """Load a dictionary of key-value pairs into the environment."""
    for key, value in env_dict.items():
        os.environ[key] = value


def _drop_quotes(value: str) -> str:
    # Handle quoted values (both single and double quotes)
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]

    return value
