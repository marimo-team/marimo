# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from marimo._config.config import MarimoConfig, merge_default_config
from marimo._server.print import (
    UTF8_SUPPORTED,
    _colorized_url,
    _get_network_url,
    _utf8,
    print_experimental_features,
    print_shutdown,
    print_startup,
)


def test_utf8() -> None:
    """Test the _utf8 function."""
    # Test with UTF8 supported
    with patch("marimo._server.print.UTF8_SUPPORTED", True):
        assert _utf8("🌊🍃") == "🌊🍃"
    
    # Test with UTF8 not supported
    with patch("marimo._server.print.UTF8_SUPPORTED", False):
        assert _utf8("🌊🍃") == ""


def test_colorized_url() -> None:
    """Test the _colorized_url function."""
    # Test with a simple URL
    with patch("marimo._server.print.bold") as mock_bold:
        mock_bold.return_value = "BOLD_URL"
        result = _colorized_url("http://localhost:8000")
        mock_bold.assert_called_once_with("http://localhost:8000")
        assert result == "BOLD_URL"
    
    # Test with a URL with a path
    with patch("marimo._server.print.bold") as mock_bold:
        mock_bold.return_value = "BOLD_URL"
        result = _colorized_url("http://localhost:8000/path")
        mock_bold.assert_called_once_with("http://localhost:8000/path")
        assert result == "BOLD_URL"
    
    # Test with a URL with a query string
    with patch("marimo._server.print.bold") as mock_bold:
        mock_bold.return_value = "BOLD_URL"
        with patch("marimo._server.print.muted") as mock_muted:
            mock_muted.return_value = "MUTED_QUERY"
            result = _colorized_url("http://localhost:8000/path?query=value")
            # The implementation separates the query part and applies muted() to it
            mock_bold.assert_called_once_with("http://localhost:8000/pathMUTED_QUERY")
            assert result == "BOLD_URL"


def test_get_network_url() -> None:
    """Test the _get_network_url function."""
    # Test with a simple URL
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-host"
        with patch("socket.gethostbyname") as mock_gethostbyname:
            mock_gethostbyname.return_value = "192.168.1.100"
            result = _get_network_url("http://localhost:8000")
            assert result == "http://192.168.1.100:8000"
    
    # Test with a URL with a path
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-host"
        with patch("socket.gethostbyname") as mock_gethostbyname:
            mock_gethostbyname.return_value = "192.168.1.100"
            result = _get_network_url("http://localhost:8000/path")
            assert result == "http://192.168.1.100:8000/path"
    
    # Test with a URL with a query string
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-host"
        with patch("socket.gethostbyname") as mock_gethostbyname:
            mock_gethostbyname.return_value = "192.168.1.100"
            result = _get_network_url("http://localhost:8000/path?query=value")
            assert result == "http://192.168.1.100:8000/path?query=value"
    
    # Test with socket.gethostbyname raising an exception
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-host"
        with patch("socket.gethostbyname") as mock_gethostbyname:
            mock_gethostbyname.side_effect = Exception("Test exception")
            result = _get_network_url("http://localhost:8000")
            assert result == "http://test-host:8000"


def test_print_startup() -> None:
    """Test the print_startup function."""
    # Test with file_name and not run
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.side_effect = lambda x: x
                with patch("marimo._server.print._colorized_url") as mock_colorized_url:
                    mock_colorized_url.return_value = "COLORIZED_URL"
                    with patch("marimo._server.print.green") as mock_green:
                        mock_green.return_value = "GREEN_TEXT"
                        print_startup(
                            file_name="test.py",
                            url="http://localhost:8000",
                            run=False,
                            new=False,
                            network=False,
                        )
                        mock_print.assert_called()
                        mock_print_tabbed.assert_any_call("➜  GREEN_TEXT: COLORIZED_URL")
    
    # Test with file_name and run
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.side_effect = lambda x: x
                with patch("marimo._server.print._colorized_url") as mock_colorized_url:
                    mock_colorized_url.return_value = "COLORIZED_URL"
                    with patch("marimo._server.print.green") as mock_green:
                        mock_green.return_value = "GREEN_TEXT"
                        print_startup(
                            file_name="test.py",
                            url="http://localhost:8000",
                            run=True,
                            new=False,
                            network=False,
                        )
                        mock_print.assert_called()
                        mock_print_tabbed.assert_any_call("➜  GREEN_TEXT: COLORIZED_URL")
    
    # Test with new=True
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.side_effect = lambda x: x
                with patch("marimo._server.print._colorized_url") as mock_colorized_url:
                    mock_colorized_url.return_value = "COLORIZED_URL"
                    with patch("marimo._server.print.green") as mock_green:
                        mock_green.return_value = "GREEN_TEXT"
                        print_startup(
                            file_name=None,
                            url="http://localhost:8000",
                            run=False,
                            new=True,
                            network=False,
                        )
                        mock_print.assert_called()
                        mock_print_tabbed.assert_any_call("➜  GREEN_TEXT: COLORIZED_URL")
    
    # Test with network=True
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.side_effect = lambda x: x
                with patch("marimo._server.print._colorized_url") as mock_colorized_url:
                    mock_colorized_url.return_value = "COLORIZED_URL"
                    with patch("marimo._server.print.green") as mock_green:
                        mock_green.return_value = "GREEN_TEXT"
                        with patch("marimo._server.print._get_network_url") as mock_get_network_url:
                            mock_get_network_url.return_value = "http://192.168.1.100:8000"
                            print_startup(
                                file_name=None,
                                url="http://localhost:8000",
                                run=False,
                                new=False,
                                network=True,
                            )
                            mock_print.assert_called()
                            mock_print_tabbed.assert_any_call("➜  GREEN_TEXT: COLORIZED_URL")
                            mock_get_network_url.assert_called_once_with("http://localhost:8000")
    
    # Test with network=True and _get_network_url raising an exception
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.side_effect = lambda x: x
                with patch("marimo._server.print._colorized_url") as mock_colorized_url:
                    mock_colorized_url.return_value = "COLORIZED_URL"
                    with patch("marimo._server.print.green") as mock_green:
                        mock_green.return_value = "GREEN_TEXT"
                        with patch("marimo._server.print._get_network_url") as mock_get_network_url:
                            mock_get_network_url.side_effect = Exception("Test exception")
                            print_startup(
                                file_name=None,
                                url="http://localhost:8000",
                                run=False,
                                new=False,
                                network=True,
                            )
                            mock_print.assert_called()
                            mock_print_tabbed.assert_any_call("➜  GREEN_TEXT: COLORIZED_URL")
                            mock_get_network_url.assert_called_once_with("http://localhost:8000")


def test_print_shutdown() -> None:
    """Test the print_shutdown function."""
    with patch("marimo._server.print.print_") as mock_print:
        with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
            with patch("marimo._server.print._utf8") as mock_utf8:
                mock_utf8.return_value = "UTF8_EMOJI"
                print_shutdown()
                mock_print.assert_called()
                mock_print_tabbed.assert_called_once()


def test_print_experimental_features() -> None:
    """Test the print_experimental_features function."""
    # Test with no experimental features
    with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
        config = merge_default_config({})
        print_experimental_features(config)
        mock_print_tabbed.assert_not_called()
    
    # Test with experimental features that have been released
    with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
        config = merge_default_config({"experimental": {"rtc": True, "chat_sidebar": True}})
        print_experimental_features(config)
        mock_print_tabbed.assert_not_called()
    
    # Test with experimental features that have not been released
    with patch("marimo._server.print.print_tabbed") as mock_print_tabbed:
        with patch("marimo._server.print._utf8") as mock_utf8:
            mock_utf8.return_value = "UTF8_EMOJI"
            with patch("marimo._server.print.green") as mock_green:
                mock_green.return_value = "GREEN_TEXT"
                config = merge_default_config({"experimental": {"new_feature": True}})
                print_experimental_features(config)
                mock_print_tabbed.assert_called_once()
                mock_utf8.assert_called_once_with("🧪")
                mock_green.assert_called_once_with("Experimental features (use with caution)")
