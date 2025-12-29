# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

import msgspec

SecretProviderType = Literal["env", "dotenv"]


class SecretKeysWithProvider(msgspec.Struct):
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
    def write_key(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def delete_key(self, key: str) -> None:
        pass
