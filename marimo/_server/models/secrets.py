# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._secrets.models import SecretKeysWithProvider, SecretProviderType


class ListSecretKeysResponse(msgspec.Struct, rename="camel"):
    """Response body for listing secret keys, grouped by provider."""

    keys: list[SecretKeysWithProvider]


class CreateSecretRequest(msgspec.Struct, rename="camel"):
    """Request body for creating a new secret."""

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


class DeleteSecretRequest(msgspec.Struct, rename="camel"):
    """Request body for deleting a secret by key."""

    key: str

    def __post_init__(self) -> None:
        assert len(self.key) > 0, "Key must be non-empty"
