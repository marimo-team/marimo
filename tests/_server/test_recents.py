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
            RecentFilesState, fallback=RecentFilesState()
        )

    def test_touch_with_config_existing_file(self) -> None:
        self.config_reader.read_toml.return_value = RecentFilesState(
            files=["old_file", "test_file"]
        )
        self.rfm.touch("test_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState()
        )
        self.config_reader.write_toml.assert_called_once_with(
            RecentFilesState(files=["test_file", "old_file"])
        )

    def test_rename_no_config(self) -> None:
        self.config_reader.read_toml.return_value = RecentFilesState(
            files=["file_1", "file_2"]
        )
        self.rfm.rename("file_2", "new_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState()
        )
        self.config_reader.write_toml.assert_called_once_with(
            RecentFilesState(files=["new_file", "file_1"])
        )

    def test_touch_with_config_max_files(self) -> None:
        original_files = [
            f"test_file_{i}" for i in range(RecentFilesManager.MAX_FILES)
        ]
        self.config_reader.read_toml.return_value = RecentFilesState(
            files=original_files[:]
        )
        self.rfm.touch("new_file")
        self.config_reader.read_toml.assert_called_once_with(
            RecentFilesState, fallback=RecentFilesState()
        )
        expected_files = ["new_file"] + original_files[:-1]
        self.config_reader.write_toml.assert_called_once_with(
            RecentFilesState(files=expected_files)
        )
