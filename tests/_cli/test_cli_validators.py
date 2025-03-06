# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import click
import pytest

from marimo._cli.cli_validators import base_url, is_file_path


class TestBaseUrl:
    def test_base_url_with_valid_input(self) -> None:
        # Test with valid input
        assert base_url(None, None, "/api") == "/api"
        assert base_url(None, None, "/api/v1") == "/api/v1"
        
    def test_base_url_with_none_or_empty(self) -> None:
        # Test with None or empty string
        assert base_url(None, None, None) == ""
        assert base_url(None, None, "") == ""
        
    def test_base_url_with_root_slash(self) -> None:
        # Test with root slash "/"
        with pytest.raises(click.BadParameter) as excinfo:
            base_url(None, None, "/")
        assert "Must not be /. This is equivalent to not setting the base URL." in str(excinfo.value)
        
    def test_base_url_without_leading_slash(self) -> None:
        # Test without leading slash
        with pytest.raises(click.BadParameter) as excinfo:
            base_url(None, None, "api")
        assert "Must start with /" in str(excinfo.value)
        
    def test_base_url_with_trailing_slash(self) -> None:
        # Test with trailing slash
        with pytest.raises(click.BadParameter) as excinfo:
            base_url(None, None, "/api/")
        assert "Must not end with /" in str(excinfo.value)


class TestIsFilePath:
    def test_is_file_path_with_valid_file(self, tmp_path: Path) -> None:
        # Create a temporary file
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        
        # Test with valid file path
        assert is_file_path(None, None, str(test_file)) == str(test_file)
        
    def test_is_file_path_with_empty_path(self) -> None:
        # Test with empty path
        with pytest.raises(click.BadParameter) as excinfo:
            is_file_path(None, None, "")
        assert "Must be a file path" in str(excinfo.value)
        
        # Test with None
        with pytest.raises(click.BadParameter) as excinfo:
            is_file_path(None, None, None)
        assert "Must be a file path" in str(excinfo.value)
        
    def test_is_file_path_with_nonexistent_file(self) -> None:
        # Test with nonexistent file
        with pytest.raises(click.BadParameter) as excinfo:
            is_file_path(None, None, "nonexistent_file.txt")
        assert "File does not exist: nonexistent_file.txt" in str(excinfo.value)
        
    def test_is_file_path_with_directory(self, tmp_path: Path) -> None:
        # Test with directory instead of file
        with pytest.raises(click.BadParameter) as excinfo:
            is_file_path(None, None, str(tmp_path))
        assert f"Not a file: {tmp_path}" in str(excinfo.value)
