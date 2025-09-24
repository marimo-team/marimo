# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.ops import SecretKeysResult
from marimo._runtime.requests import (
    ListSecretKeysRequest,
    RefreshSecretsRequest,
)
from marimo._secrets.secrets import get_secret_keys

if TYPE_CHECKING:
    from marimo._runtime.runtime.kernel import Kernel


class SecretsCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    async def list_secrets(self, request: ListSecretKeysRequest) -> None:
        secrets = get_secret_keys(
            self._kernel.user_config, self._kernel._original_environ
        )
        SecretKeysResult(
            request_id=request.request_id, secrets=secrets
        ).broadcast()

    async def refresh_secrets(self, request: RefreshSecretsRequest) -> None:
        del request
        self._kernel.load_dotenv()
