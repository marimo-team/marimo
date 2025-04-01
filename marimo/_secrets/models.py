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
    def set_key(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def delete_key(self, key: str) -> None:
        pass
