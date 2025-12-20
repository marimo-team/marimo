# Copyright 2024 Marimo. All rights reserved.
"""Tests for token_manager module."""

from __future__ import annotations

import pytest

from marimo._server.model import SessionMode
from marimo._server.sessions.token_manager import TokenManager
from marimo._server.tokens import AuthToken, SkewProtectionToken


def test_token_manager_edit_mode_random_tokens() -> None:
    """Test that edit mode creates random tokens when no auth token provided."""
    manager = TokenManager(mode=SessionMode.EDIT)

    assert manager.mode == SessionMode.EDIT
    assert manager.auth_token is not None
    assert manager.skew_protection_token is not None

    # Verify they are different from another instance
    manager2 = TokenManager(mode=SessionMode.EDIT)
    assert manager.auth_token != manager2.auth_token
    assert manager.skew_protection_token != manager2.skew_protection_token


def test_token_manager_edit_mode_with_provided_token() -> None:
    """Test that edit mode uses provided auth token."""
    provided_token = AuthToken.random()
    manager = TokenManager(mode=SessionMode.EDIT, auth_token=provided_token)

    assert manager.auth_token == provided_token
    # Skew protection should still be random
    assert manager.skew_protection_token is not None


def test_token_manager_run_mode_code_based_tokens() -> None:
    """Test that run mode creates code-based tokens."""
    source_code = "print('hello world')"
    manager = TokenManager(mode=SessionMode.RUN, source_code=source_code)

    assert manager.mode == SessionMode.RUN
    assert manager.auth_token is not None
    assert manager.skew_protection_token is not None

    # Verify they are consistent for the same code
    manager2 = TokenManager(mode=SessionMode.RUN, source_code=source_code)
    assert str(manager.auth_token) == str(manager2.auth_token)
    assert str(manager.skew_protection_token) == str(
        manager2.skew_protection_token
    )


def test_token_manager_run_mode_requires_source_code() -> None:
    """Test that run mode raises error without source code."""
    with pytest.raises(ValueError, match="source_code is required"):
        TokenManager(mode=SessionMode.RUN)


def test_token_manager_run_mode_with_provided_token() -> None:
    """Test that run mode uses provided auth token."""
    source_code = "print('test')"
    provided_token = AuthToken.random()
    manager = TokenManager(
        mode=SessionMode.RUN,
        auth_token=provided_token,
        source_code=source_code,
    )

    assert str(manager.auth_token) == str(provided_token)
    # Skew protection should still be code-based
    expected_skew = SkewProtectionToken.from_code(source_code)
    assert str(manager.skew_protection_token) == str(expected_skew)


def test_token_manager_validate_auth() -> None:
    """Test auth token validation."""
    manager = TokenManager(mode=SessionMode.EDIT)

    # Valid token should pass
    assert manager.validate_auth(manager.auth_token)

    # Invalid token should fail
    invalid_token = AuthToken.random()
    assert not manager.validate_auth(invalid_token)


def test_token_manager_validate_skew() -> None:
    """Test skew protection token validation."""
    manager = TokenManager(mode=SessionMode.EDIT)

    # Valid token should pass
    assert manager.validate_skew(manager.skew_protection_token)

    # Invalid token should fail
    invalid_token = SkewProtectionToken.random()
    assert not manager.validate_skew(invalid_token)
