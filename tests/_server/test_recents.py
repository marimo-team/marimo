import unittest
from unittest.mock import Mock, patch

from marimo._server.recents import RecentFilesManager, RecentFilesState


class TestRecentFilesManager(unittest.TestCase):
    @patch("marimo._server.recents.ConfigReader")
    def setUp(self, mock_config_reader: Mock) -> None:
        self.config_reader = mock_config_reader
        self.rfm = RecentFilesManager()
        self.rfm.config = self.config_reader

    def test_touch_no_config(self) -> None:
        self.rfm.touch("test_file")
        self.config_reader.for_filename.assert_called_once_with(
            RecentFilesManager.LOCATION
        )
        self.config_reader.for_filename.return_value.read_toml.assert_not_called()
        self.config_reader.for_filename.return_value.write_toml.assert_not_called()

    def test_touch_with_config(self) -> None:
        self.rfm.touch("test_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState(files=[])
        )

    def test_touch_with_config_existing_file(self) -> None:
        self.config_reader.read_toml.return_value = RecentFilesState(
            files=["test_file", "old_file"]
        )
        self.rfm.touch("test_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState(files=[])
        )
        self.config_reader.write_toml.assert_called_once_with(
            RecentFilesState(files=["old_file", "test_file"])
        )

    def test_touch_with_config_max_files(self) -> None:
        self.config_reader.read_toml.return_value = RecentFilesState(
            files=["test_file"] * (RecentFilesManager.MAX_FILES - 1)
        )
        self.rfm.touch("test_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState(files=[])
        )
        self.config_reader.write_toml.assert_called_once_with(
            RecentFilesState(
                files=["test_file"] * RecentFilesManager.MAX_FILES
            )
        )
