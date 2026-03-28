# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from marimo._session.app_host.pool import AppHostPool


@pytest.mark.requires("zmq")
class TestAppHostPoolRespawnDead:
    def test_respawns_dead_host(self) -> None:
        """_create_locked shuts down dead host and creates a new one."""
        pool = AppHostPool(sandbox=False)

        dead_host = MagicMock()
        dead_host.is_alive.return_value = False

        new_host = MagicMock()
        new_host.is_alive.return_value = True

        abs_path = os.path.abspath("/tmp/test_respawn.py")
        pool._workers[abs_path] = dead_host

        with patch(
            "marimo._session.app_host.pool.AppHost",
            return_value=new_host,
        ):
            result = pool.get_or_create("/tmp/test_respawn.py")

        dead_host.shutdown.assert_called_once()
        assert result is new_host
        assert pool._workers[abs_path] is new_host
