# Copyright 2025 Marimo. All rights reserved.
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
    name: str

    def __post_init__(self) -> None:
        assert len(self.key) > 0, "Key must be non-empty"
        assert len(self.value) > 0, "Value must be non-empty"
        # Validate key doesn't contain whitespace
        if any(char.isspace() for char in self.key):
            raise ValueError("Key cannot contain spaces or whitespace")


@dataclass
class DeleteSecretRequest:
    key: str

    def __post_init__(self) -> None:
        assert len(self.key) > 0, "Key must be non-empty"
