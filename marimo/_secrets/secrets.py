from __future__ import annotations

from marimo._secrets.env_provider import EnvSecretsProvider
from marimo._secrets.models import SecretKeysWithProvider


def get_secret_keys() -> list[SecretKeysWithProvider]:
    PROVIDERS = [EnvSecretsProvider()]

    results: list[SecretKeysWithProvider] = []
    for provider in PROVIDERS:
        results.append(
            SecretKeysWithProvider(provider="env", keys=provider.get_keys())
        )
    return results
