# Copyright 2026 Marimo. All rights reserved.
"""Token management for authentication and skew protection.

Manages creation and validation of auth tokens and skew protection tokens
based on session mode.
"""

from __future__ import annotations

from typing import Optional

from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._session.model import SessionMode


class TokenManager:
    """Manages authentication and skew protection tokens."""

    def __init__(
        self,
        mode: SessionMode,
        auth_token: Optional[AuthToken] = None,
        source_code: Optional[str] = None,
    ) -> None:
        """Initialize token manager.

        Args:
            mode: The session mode (edit or run)
            auth_token: Optional pre-configured auth token
            source_code: Source code for generating code-based tokens in run mode
        """
        self.mode = mode

        # Create tokens based on mode
        if mode == SessionMode.EDIT:
            # In edit mode, use random tokens or provided token
            self.auth_token = (
                AuthToken.random() if auth_token is None else auth_token
            )
            self.skew_protection_token = SkewProtectionToken.random()
        else:
            # In run mode, use code-based tokens for consistency across instances
            if source_code is None:
                raise ValueError(
                    "source_code is required for run mode token generation"
                )
            self.auth_token = (
                AuthToken.from_code(source_code)
                if auth_token is None
                else auth_token
            )
            self.skew_protection_token = SkewProtectionToken.from_code(
                source_code
            )

    def validate_auth(self, token: AuthToken) -> bool:
        """Validate an auth token."""
        return token == self.auth_token

    def validate_skew(self, token: SkewProtectionToken) -> bool:
        """Validate a skew protection token."""
        return token == self.skew_protection_token
