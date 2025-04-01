from __future__ import annotations

from pathlib import Path

from marimo._secrets.load_dotenv import read_dotenv_with_fallback
from marimo._secrets.models import SecretProvider


class EnvSecretsProvider(SecretProvider):
    type = "env"

    def __init__(self, original_environ: dict[str, str]):
        self.original_environ = original_environ

    @property
    def name(self) -> str:
        return "Environment variables"

    def get_keys(self) -> set[str]:
        return set(self.original_environ.keys())

    def write_key(self, key: str, value: str) -> None:
        del key, value
        raise NotImplementedError("Cannot set keys for env provider")

    def delete_key(self, key: str) -> None:
        del key
        raise NotImplementedError("Cannot delete keys for env provider")


class DotEnvSecretsProvider(SecretProvider):
    type = "dotenv"

    def __init__(self, file: str):
        self.file = file

    @property
    def name(self) -> str:
        return Path(self.file).name

    def get_keys(self) -> set[str]:
        env_dict = read_dotenv_with_fallback(self.file)
        return set(env_dict.keys())

    def write_key(self, key: str, value: str) -> None:
        filepath = Path(self.file)
        if not filepath.exists():
            # If is `.env`, then create it.
            if filepath.name == ".env":
                filepath.touch()
            else:
                raise FileNotFoundError(f"File {filepath} does not exist")

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Check if file ends with a newline
        ends_with_newline = content.endswith("\n")

        # Note: there could be a race condition here, but it's unlikely
        with open(filepath, "a", encoding="utf-8") as f:
            # Add a newline if the file doesn't end with one
            if content and not ends_with_newline:
                f.write("\n")

            # Escape quotes in value if needed
            escaped_value = value.replace('"', '\\"')
            f.write(f'{key}="{escaped_value}"\n')

    def delete_key(self, key: str) -> None:
        del key
        raise NotImplementedError
