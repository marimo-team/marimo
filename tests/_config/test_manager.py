from __future__ import annotations

import unittest
from functools import wraps
from typing import Any, Callable, TypeVar
from unittest.mock import patch

from marimo._config.config import PartialMarimoConfig, merge_default_config
from marimo._config.manager import UserConfigManager
from marimo._config.utils import load_config

F = TypeVar("F", bound=Callable[..., Any])


def restore_config(f: F) -> F:
    config = load_config()

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        finally:
            UserConfigManager().save_config(config)

    return wrapper  # type: ignore


class TestUserConfigManager(unittest.TestCase):
    @restore_config
    @patch("tomlkit.dump")
    @patch("marimo._config.manager.load_config")
    def test_save_config(self, mock_load: Any, mock_dump: Any) -> None:
        mock_config = merge_default_config(PartialMarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        result = manager.save_config(mock_config)

        mock_load.assert_called_once()
        assert result == manager.config

        assert mock_dump.mock_calls[0][1][0] == result

    @restore_config
    @patch("tomlkit.dump")
    @patch("marimo._config.manager.load_config")
    def test_can_save_secrets(self, mock_load: Any, mock_dump: Any) -> None:
        mock_config = merge_default_config(PartialMarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        manager.save_config(
            merge_default_config(
                PartialMarimoConfig(
                    ai={"open_ai": {"api_key": "super_secret"}}
                )
            )
        )

        assert (
            mock_dump.mock_calls[0][1][0]["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

        # Do not overwrite secrets
        manager.save_config(
            merge_default_config(
                PartialMarimoConfig(ai={"open_ai": {"api_key": "********"}})
            )
        )
        assert (
            mock_dump.mock_calls[1][1][0]["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

    @restore_config
    @patch("marimo._config.manager.load_config")
    def test_can_read_secrets(self, mock_load: Any) -> None:
        mock_config = merge_default_config(
            PartialMarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
        )
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        assert manager.get_config()["ai"]["open_ai"]["api_key"] == "********"
        assert (
            manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

    @restore_config
    @patch("marimo._config.manager.load_config")
    def test_get_config(self, mock_load: Any) -> None:
        mock_config = merge_default_config(PartialMarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        result = manager.get_config()

        mock_load.assert_called_once()
        assert result == manager.config
