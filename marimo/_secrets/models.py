# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import msgspec

SecretProviderType = Literal["env", "dotenv"]


class SecretKeysWithProvider(msgspec.Struct):
    """Associates a set of secret key names with their provider."""

    provider: SecretProviderType
    name: str
    keys: list[str]


class SecretProvider(ABC):
    """Abstract base class for secret storage backends (e.g. env vars, dotenv)."""

    type: SecretProviderType

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the display name of this provider."""
        pass

    @abstractmethod
    def get_keys(self) -> set[str]:
        """Return the set of all secret key names available from this provider."""
        pass

    @abstractmethod
    def write_key(self, key: str, value: str) -> None:
        """Persist a secret key/value pair to this provider's storage."""
        pass

    @abstractmethod
    def delete_key(self, key: str) -> None:
        """Remove a secret key from this provider's storage."""
        pass
