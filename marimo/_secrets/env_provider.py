from __future__ import annotations

from marimo._secrets.models import SecretProvider


class EnvSecretsProvider(SecretProvider):
    type = "env"

    def get_keys(self) -> list[str]:
        import os

        return list(os.environ.keys())
