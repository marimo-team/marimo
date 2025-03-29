from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

SecretProviderType = Literal["env"]


@dataclass
class SecretKeysWithProvider:
    provider: SecretProviderType
    keys: list[str]


class SecretProvider(ABC):
    type: SecretProviderType

    @abstractmethod
    def get_keys(self) -> list[str]:
        pass

    @abstractmethod
    def set_key(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def delete_key(self, key: str) -> None:
        pass
