from __future__ import annotations

from marimo._secrets.models import SecretProvider


class EnvSecretsProvider(SecretProvider):
    type = "env"

    def get_keys(self) -> list[str]:
        import os

        return list(os.environ.keys())

    def set_key(self, key: str, value: str) -> None:
        del key, value
        raise NotImplementedError

    def delete_key(self, key: str) -> None:
        del key
        raise NotImplementedError
