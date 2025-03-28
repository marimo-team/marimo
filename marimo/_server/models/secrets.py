from __future__ import annotations

from dataclasses import dataclass

from marimo._secrets.models import SecretKeysWithProvider, SecretProviderType


@dataclass
class ListSecretKeysResponse:
    keys: list[SecretKeysWithProvider]


@dataclass
class CreateSecretRequest:
    key: str
    value: str
    provider: SecretProviderType

    def __post_init__(self) -> None:
        assert len(self.key) > 0, "Key must be non-empty"
        assert len(self.value) > 0, "Value must be non-empty"


@dataclass
class DeleteSecretRequest:
    key: str

    def __post_init__(self) -> None:
        assert len(self.key) > 0, "Key must be non-empty"
