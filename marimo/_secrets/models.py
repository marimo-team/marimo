from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

SecretProviderType = Literal["env", "dotenv"]


@dataclass
class SecretKeysWithProvider:
    provider: SecretProviderType
    name: str
    keys: list[str]


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


class SecretProvider(ABC):
    type: SecretProviderType

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_keys(self) -> set[str]:
        pass

    @abstractmethod
    def write_key(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def delete_key(self, key: str) -> None:
        pass
