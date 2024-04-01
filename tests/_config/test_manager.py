import unittest
from typing import Any
from unittest.mock import patch

from marimo._config.config import merge_default_config
from marimo._config.manager import MarimoConfig, UserConfigManager


class TestUserConfigManager(unittest.TestCase):
    @patch("tomlkit.dump")
    @patch("marimo._config.manager.load_config")
    def test_save_config(self, mock_load: Any, mock_dump: Any) -> None:
        mock_config = merge_default_config(MarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        result = manager.save_config(mock_config)

        mock_load.assert_called_once()
        assert result == manager.config

        assert mock_dump.mock_calls[0][1][0] == result

    @patch("tomlkit.dump")
    @patch("marimo._config.manager.load_config")
    def test_can_save_secrets(self, mock_load: Any, mock_dump: Any) -> None:
        mock_config = merge_default_config(MarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        manager.save_config(
            merge_default_config(
                MarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
            )
        )

        assert (
            mock_dump.mock_calls[0][1][0]["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

        # Do not overwrite secrets
        manager.save_config(
            merge_default_config(
                MarimoConfig(ai={"open_ai": {"api_key": "********"}})
            )
        )
        assert (
            mock_dump.mock_calls[1][1][0]["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

    @patch("marimo._config.manager.load_config")
    def test_can_read_secrets(self, mock_load: Any) -> None:
        mock_config = merge_default_config(
            MarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
        )
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        assert manager.get_config()["ai"]["open_ai"]["api_key"] == "********"
        assert (
            manager.get_config(hide_secrets=False)["ai"]["open_ai"]["api_key"]
            == "super_secret"
        )

    @patch("marimo._config.manager.load_config")
    def test_get_config(self, mock_load: Any) -> None:
        mock_config = merge_default_config(MarimoConfig())
        mock_load.return_value = mock_config
        manager = UserConfigManager()

        result = manager.get_config()

        mock_load.assert_called_once()
        assert result == manager.config
