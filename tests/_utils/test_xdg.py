# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from marimo._utils.platform import is_windows
from marimo._utils.xdg import (
    home_path,
    marimo_cache_dir,
    marimo_config_path,
    marimo_log_dir,
    marimo_state_dir,
    xdg_cache_home,
    xdg_config_home,
    xdg_state_home,
)


class TestHomePathFunction:
    """Test home_path function behavior."""

    @patch("pathlib.Path.home")
    def test_home_path_normal(self, mock_home) -> None:
        """Test home_path returns home directory when available."""
        expected_home = Path("/home/user")
        mock_home.return_value = expected_home
        result = home_path()
        assert result == expected_home.resolve()

    @patch("pathlib.Path.home")
    def test_home_path_runtime_error_fallback(self, mock_home) -> None:
        """Test home_path falls back to /tmp on RuntimeError."""
        mock_home.side_effect = RuntimeError("Unable to get home directory")
        result = home_path()
        assert result == Path("/tmp")


class TestXDGBasicFunctions:
    """Test basic XDG directory functions."""

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_xdg_config_home_default(self, mock_home_path) -> None:
        """Test default XDG config home returns ~/.config."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_config_home()
        assert result == Path("/home/user/.config")

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"})
    def test_xdg_config_home_env_set(self) -> None:
        """Test XDG config home respects XDG_CONFIG_HOME environment variable."""
        result = xdg_config_home()
        assert result == Path("/custom/config")

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_xdg_cache_home_default(self, mock_home_path) -> None:
        """Test default XDG cache home returns ~/.cache."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_cache_home()
        assert result == Path("/home/user/.cache")

    @patch.dict(os.environ, {"XDG_CACHE_HOME": "/custom/cache"})
    def test_xdg_cache_home_env_set(self) -> None:
        """Test XDG cache home respects XDG_CACHE_HOME environment variable."""
        result = xdg_cache_home()
        assert result == Path("/custom/cache")

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    @patch("os.name", "posix")
    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_xdg_state_home_posix_default(self, mock_home_path) -> None:
        """Test default XDG state home on POSIX systems."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_state_home()
        assert result == Path("/home/user/.local/state")

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    @patch("os.name", "posix")
    @patch.dict(os.environ, {"XDG_STATE_HOME": "/custom/state"})
    def test_xdg_state_home_posix_env_set(self) -> None:
        """Test XDG state home on POSIX respects XDG_STATE_HOME environment variable."""
        result = xdg_state_home()
        assert result == Path("/custom/state")

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_xdg_state_home_non_posix(self) -> None:
        """Test XDG state home on non-POSIX systems returns home directory."""
        with patch("marimo._utils.xdg.home_path") as mock_home_path:
            mock_home_path.return_value = Path.home()
            result = xdg_state_home()
            # On Windows, should return home directory directly
            assert result == Path.home()


class TestMarimoSpecificFunctions:
    """Test marimo-specific XDG functions."""

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_marimo_config_path_default(self, mock_home_path) -> None:
        """Test marimo config path with default XDG config home."""
        mock_home_path.return_value = Path("/home/user")
        result = marimo_config_path()
        assert result == Path("/home/user/.config/marimo/marimo.toml")

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"})
    def test_marimo_config_path_custom_xdg(self) -> None:
        """Test marimo config path with custom XDG_CONFIG_HOME."""
        result = marimo_config_path()
        assert result == Path("/custom/config/marimo/marimo.toml")

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_marimo_cache_dir_default(self, mock_home_path) -> None:
        """Test marimo cache directory with default XDG cache home."""
        mock_home_path.return_value = Path("/home/user")
        result = marimo_cache_dir()
        assert result == Path("/home/user/.cache/marimo")

    @patch.dict(os.environ, {"XDG_CACHE_HOME": "/custom/cache"})
    def test_marimo_cache_dir_custom_xdg(self) -> None:
        """Test marimo cache directory with custom XDG_CACHE_HOME."""
        result = marimo_cache_dir()
        assert result == Path("/custom/cache/marimo")

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    @patch("os.name", "posix")
    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_marimo_state_dir_posix_default(self, mock_home_path) -> None:
        """Test marimo state directory on POSIX with default XDG state home."""
        mock_home_path.return_value = Path("/home/user")
        result = marimo_state_dir()
        assert result == Path("/home/user/.local/state/marimo")

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    @patch("os.name", "posix")
    @patch.dict(os.environ, {"XDG_STATE_HOME": "/custom/state"})
    def test_marimo_state_dir_posix_custom_xdg(self) -> None:
        """Test marimo state directory on POSIX with custom XDG_STATE_HOME."""
        result = marimo_state_dir()
        assert result == Path("/custom/state/marimo")

    @pytest.mark.skipif(not is_windows(), reason="Windows-specific test")
    def test_marimo_state_dir_non_posix(self) -> None:
        """Test marimo state directory on non-POSIX systems."""
        with patch("marimo._utils.xdg.home_path") as mock_home_path:
            mock_home_path.return_value = Path.home()
            result = marimo_state_dir()
            # On Windows, should return home/.marimo
            assert result == Path.home() / ".marimo"

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {}, clear=True)
    def test_marimo_log_dir_default(self, mock_home_path) -> None:
        """Test marimo log directory with default XDG cache home."""
        mock_home_path.return_value = Path("/home/user")
        result = marimo_log_dir()
        assert result == Path("/home/user/.cache/marimo/logs")

    @patch.dict(os.environ, {"XDG_CACHE_HOME": "/custom/cache"})
    def test_marimo_log_dir_custom_xdg(self) -> None:
        """Test marimo log directory with custom XDG_CACHE_HOME."""
        result = marimo_log_dir()
        assert result == Path("/custom/cache/marimo/logs")


class TestEnvironmentVariableHandling:
    """Test environment variable handling edge cases."""

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {"XDG_CONFIG_HOME": ""})
    def test_empty_xdg_config_home(self, mock_home_path) -> None:
        """Test behavior with empty XDG_CONFIG_HOME."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_config_home()
        assert result == Path("/home/user/.config")

    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {"XDG_CACHE_HOME": ""})
    def test_empty_xdg_cache_home(self, mock_home_path) -> None:
        """Test behavior with empty XDG_CACHE_HOME."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_cache_home()
        assert result == Path("/home/user/.cache")

    @pytest.mark.skipif(is_windows(), reason="POSIX-specific test")
    @patch("os.name", "posix")
    @patch("marimo._utils.xdg.home_path")
    @patch.dict(os.environ, {"XDG_STATE_HOME": ""})
    def test_empty_xdg_state_home_posix(self, mock_home_path) -> None:
        """Test behavior with empty XDG_STATE_HOME on POSIX."""
        mock_home_path.return_value = Path("/home/user")
        result = xdg_state_home()
        assert result == Path("/home/user/.local/state")

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative/path"})
    def test_relative_paths_in_env_vars(self) -> None:
        """Test behavior with relative paths in environment variables."""
        result = xdg_config_home()
        assert result == Path("relative/path")

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "  /path/with/spaces  "})
    def test_whitespace_in_env_vars(self) -> None:
        """Test behavior with whitespace in environment variables."""
        result = xdg_config_home()
        assert result == Path("  /path/with/spaces  ")


class TestIntegration:
    """Integration tests using temporary directories."""

    def test_with_temp_directories(self) -> None:
        """Test XDG functions work with real temporary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / "config"
            cache_dir = temp_path / "cache"
            state_dir = temp_path / "state"

            # Create directories
            config_dir.mkdir()
            cache_dir.mkdir()
            state_dir.mkdir()

            with patch.dict(
                os.environ,
                {
                    "XDG_CONFIG_HOME": str(config_dir),
                    "XDG_CACHE_HOME": str(cache_dir),
                    "XDG_STATE_HOME": str(state_dir),
                },
            ):
                # Test basic functions
                assert xdg_config_home() == config_dir
                assert xdg_cache_home() == cache_dir

                if not is_windows():
                    with patch("os.name", "posix"):
                        assert xdg_state_home() == state_dir

                # Test marimo functions
                assert (
                    marimo_config_path()
                    == config_dir / "marimo" / "marimo.toml"
                )
                assert marimo_cache_dir() == cache_dir / "marimo"
                assert marimo_log_dir() == cache_dir / "marimo" / "logs"

                if not is_windows():
                    with patch("os.name", "posix"):
                        assert marimo_state_dir() == state_dir / "marimo"

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/test/config"})
    def test_path_composition(self) -> None:
        """Test that Path objects compose correctly."""
        config_path = marimo_config_path()

        # Test that we can use Path methods
        assert config_path.parent == Path("/test/config/marimo")
        assert config_path.name == "marimo.toml"
        assert config_path.suffix == ".toml"

        # Test that we can compose new paths
        backup_path = config_path.with_suffix(".toml.bak")
        assert backup_path == Path("/test/config/marimo/marimo.toml.bak")

    @patch.dict(os.environ, {})
    def test_return_types(self) -> None:
        """Test that all functions return the correct types."""
        # Basic XDG functions should return Path objects
        assert isinstance(xdg_config_home(), Path)
        assert isinstance(xdg_cache_home(), Path)
        assert isinstance(xdg_state_home(), Path)

        # Marimo functions should return Path objects
        assert isinstance(marimo_config_path(), Path)
        assert isinstance(marimo_cache_dir(), Path)
        assert isinstance(marimo_state_dir(), Path)
        assert isinstance(marimo_log_dir(), Path)
