# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.requests import SetUserConfigRequest
from marimo._runtime.runtime import Kernel
from tests._server.conftest import get_user_config_manager
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient


class MockKernel(Kernel):
    """Mock kernel that inherits from real Kernel to test actual code paths"""

    def __init__(self, user_config):
        # Don't call super().__init__ to avoid full kernel setup
        # Just set up the minimal attributes needed for testing
        self.user_config = user_config
        self.reactive_execution_mode = user_config["runtime"]["on_cell_change"]

        # Add attributes needed by _update_runtime_from_user_config
        self.module_reloader = None
        self.module_watcher = None
        self.graph = None
        self.stream = None

        class MockPackagesCallbacks:
            def update_package_manager(self, manager):
                pass

        self.packages_callbacks = MockPackagesCallbacks()

        # Mock callback function
        self._execute_stale_cells_callback = lambda: None

    @property
    def marimo_config(self):
        """This simulates the context.marimo_config property"""
        return self.user_config


SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def test_save_user_config_no_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_save_user_config_with_session(client: TestClient) -> None:
    user_config_manager = get_user_config_manager(client)
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": user_config_manager.get_config(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


def test_partial_config_breaks_kernel_update():
    """
    Test that partial config would break kernel update (demonstrates the bug)

    This test shows what would happen if we sent partial config directly to kernel
    without the fix - the _update_runtime_from_user_config method would fail.
    """
    # Start with complete config
    kernel = MockKernel(DEFAULT_CONFIG)

    # Create a partial config that's missing required fields
    partial_config = {
        "display": {
            "theme": "light",
        },
        "runtime": {
            "auto_instantiate": True,
            # Missing other required fields like auto_reload, on_cell_change, etc.
        },
        # Missing entire package_management section!
    }

    # This would fail if we sent partial config directly to kernel
    request = SetUserConfigRequest(config=partial_config)

    # The kernel update should fail because partial config is missing required fields
    with pytest.raises(KeyError):
        kernel.set_user_config(request)


@with_session(SESSION_ID)
def test_save_user_config_with_partial_config(client: TestClient) -> None:
    """
    Test that save_user_config endpoint works correctly with partial config

    This is a regression test for the KeyError: 'output_max_bytes' bug.
    Before the fix, sending partial config would cause runtime errors when
    the kernel tried to access missing config fields.
    """
    # Create a partial config that's missing required runtime fields
    partial_config = {
        "display": {
            "theme": "light",  # User changed theme
        },
        "runtime": {
            "auto_instantiate": True,  # User changed this setting
            # Missing output_max_bytes and other required fields!
        },
    }

    # This should work without errors after the fix
    response = client.post(
        "/api/kernel/save_user_config",
        headers=HEADERS,
        json={
            "config": partial_config,
        },
    )

    # Verify the endpoint succeeds
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()
