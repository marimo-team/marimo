# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import SecretKeysResultNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._secrets.secrets import get_secret_keys

if TYPE_CHECKING:
    from marimo._runtime.commands import (
        ListSecretKeysCommand,
        RefreshSecretsCommand,
    )
    from marimo._runtime.runtime import Kernel


class SecretsCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    async def list_secrets(self, request: ListSecretKeysCommand) -> None:
        secrets = get_secret_keys(
            self._kernel.user_config, self._kernel._original_environ
        )
        broadcast_notification(
            SecretKeysResultNotification(
                request_id=request.request_id, secrets=secrets
            ),
        )

    async def refresh_secrets(self, request: RefreshSecretsCommand) -> None:
        del request
        self._kernel.load_dotenv()
