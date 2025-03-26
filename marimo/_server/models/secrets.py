from __future__ import annotations

from dataclasses import dataclass

from marimo._secrets.models import SecretKeysWithProvider


@dataclass
class ListSecretKeysResponse:
    keys: list[SecretKeysWithProvider]
