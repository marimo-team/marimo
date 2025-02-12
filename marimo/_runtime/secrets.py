# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


class SecretManager:
    """Manages secrets for Marimo notebooks."""

    def __init__(self, app_id: str, allow_secrets: bool = False):
        self.app_id = app_id
        self._prefix = f"MARIMO_{app_id}_"
        self.allow_secrets = allow_secrets
        # Track which secrets have been approved in this session
        self._approved_secrets: set[str] = set()

    def _check_secrets_enabled(self) -> None:
        """Check if secrets are enabled for this app"""
        if not self.allow_secrets:
            raise RuntimeError(
                "Secrets are disabled for this app. "
                "Enable them by passing allow_secrets=True to App()"
            )

    def set_secret(self, key: str, value: str = None) -> None:
        """Store a secret securely.

        Args:
            key: The name of the secret
            value: The secret value to store. If None, will prompt for input.

        Raises:
            ValueError: If key or value is empty
            RuntimeError: If secret storage fails
        """
        self._check_secrets_enabled()
        if not key:
            raise ValueError("Key must not be empty")

        if value is None:
            import getpass

            value = getpass.getpass(f"Enter value for secret '{key}': ")

        if not value:
            raise ValueError("Value must not be empty")

        # Check if key already exists
        env_key = self._prefix + key.upper()
        if env_key in os.environ:
            import getpass

            confirm = getpass.getpass(
                f"Secret '{key}' already exists. Override? (y/n): "
            )
            if confirm.lower() == "n":
                return

        try:
            os.environ[env_key] = value
        except Exception as e:
            LOGGER.error(f"Failed to store secret: {e}")
            raise RuntimeError(f"Failed to store secret: {e}") from e

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret.

        Args:
            key: The name of the secret to retrieve

        Returns:
            The secret value if found and confirmed, None otherwise

        Raises:
            ValueError: If key is empty
            RuntimeError: If secrets are disabled
        """
        self._check_secrets_enabled()
        if not key:
            raise ValueError("Key must not be empty")

        try:
            env_key = self._prefix + key.upper()
            value = os.environ.get(env_key)

            if value is not None and env_key not in self._approved_secrets:
                import getpass

                confirm = getpass.getpass(
                    f"Approve access to secret '{key}'? (y/n): "
                ).lower()
                if confirm != "y":
                    return None
                self._approved_secrets.add(env_key)

            return value
        except Exception as e:
            LOGGER.error(f"Failed to retrieve secret: {e}")
            return None

    def delete_secret(self, key: str) -> None:
        """Delete a secret.

        Args:
            key: The name of the secret to delete

        Raises:
            ValueError: If key is empty
        """
        self._check_secrets_enabled()
        if not key:
            raise ValueError("Key must not be empty")

        try:
            env_key = self._prefix + key.upper()
            if env_key in os.environ:
                del os.environ[env_key]
        except Exception as e:
            LOGGER.warning(f"Failed to delete secret: {e}")
