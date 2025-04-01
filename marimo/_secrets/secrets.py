from __future__ import annotations

from marimo._config.config import MarimoConfig
from marimo._secrets.env_provider import (
    DotEnvSecretsProvider,
    EnvSecretsProvider,
)
from marimo._secrets.models import SecretKeysWithProvider, SecretProvider


def get_secret_keys(
    config: MarimoConfig, original_environ: dict[str, str]
) -> list[SecretKeysWithProvider]:
    providers: list[SecretProvider] = [EnvSecretsProvider(original_environ)]

    # Add dotenv providers
    dotenvs: list[str] = config.get("runtime", {}).get("dotenv", [])
    if dotenvs and isinstance(dotenvs, list):
        providers.extend(DotEnvSecretsProvider(dotenv) for dotenv in dotenvs)

    results: list[SecretKeysWithProvider] = []
    seen_keys: set[str] = set()
    for provider in providers:
        keys = provider.get_keys()
        results.append(
            SecretKeysWithProvider(
                # We remove duplicates by only adding keys that haven't been
                # seen yet.
                # This is because we don't override existing keys in the
                # environment.
                provider=provider.type,
                name=provider.name,
                keys=sorted(keys - seen_keys),
            )
        )
        seen_keys.update(keys)

    return results
