# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
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
    result = _colorized_url("http://localhost:8000")
    assert "localhost:8000" in result
    
    # Test with a URL with a path
    result = _colorized_url("http://localhost:8000/path")
    assert "localhost:8000/path" in result
    
    # Test with a URL with a query string
    result = _colorized_url("http://localhost:8000/path?query=value")
    assert "localhost:8000/path" in result
    assert "query=value" in result


def test_get_network_url() -> None:
    """Test the _get_network_url function."""
    # Test with a simple URL
    with patch("socket.gethostname") as mock_gethostname:
        mock_gethostname.return_value = "test-host"
        with patch("socket.gethostbyname") as mock_gethostbyname:
            mock_gethostbyname.return_value = "192.168.1.100"
            result = _get_network_url("http://localhost:8000")
            assert result == "http://192.168.1.100:8000"
    
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
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name="test.py",
            url="http://localhost:8000",
            run=False,
            new=False,
            network=False,
        )
        output = buf.getvalue()
        assert "Edit test.py in your browser" in output
        assert "URL" in output
        assert "localhost:8000" in output
    
    # Test with file_name and run
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name="test.py",
            url="http://localhost:8000",
            run=True,
            new=False,
            network=False,
        )
        output = buf.getvalue()
        assert "Running test.py" in output
        assert "URL" in output
        assert "localhost:8000" in output
    
    # Test with new=True
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name=None,
            url="http://localhost:8000",
            run=False,
            new=True,
            network=False,
        )
        output = buf.getvalue()
        assert "Create a new notebook" in output
        assert "URL" in output
        assert "localhost:8000" in output
    
    # Test with file_name=None and new=False
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name=None,
            url="http://localhost:8000",
            run=False,
            new=False,
            network=False,
        )
        output = buf.getvalue()
        assert "Create or edit notebooks" in output
        assert "URL" in output
        assert "localhost:8000" in output
    
    # Test with network=True
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch("marimo._server.print._get_network_url") as mock_get_network_url:
            mock_get_network_url.return_value = "http://192.168.1.100:8000"
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=True,
            )
            output = buf.getvalue()
            assert "Create or edit notebooks" in output
            assert "URL" in output
            assert "localhost:8000" in output
            assert "Network" in output
            assert "192.168.1.100:8000" in output
            mock_get_network_url.assert_called_once_with("http://localhost:8000")
    
    # Test with network=True and _get_network_url raising an exception
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch("marimo._server.print._get_network_url") as mock_get_network_url:
            mock_get_network_url.side_effect = Exception("Test exception")
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=True,
            )
            output = buf.getvalue()
            assert "Create or edit notebooks" in output
            assert "URL" in output
            assert "localhost:8000" in output
            assert "Network" not in output
            mock_get_network_url.assert_called_once_with("http://localhost:8000")


def test_print_shutdown() -> None:
    """Test the print_shutdown function."""
    with io.StringIO() as buf, redirect_stdout(buf):
        print_shutdown()
        output = buf.getvalue()
        assert "Thanks for using marimo" in output


def test_print_experimental_features() -> None:
    """Test the print_experimental_features function."""
    # Test with no experimental features
    with io.StringIO() as buf, redirect_stdout(buf):
        config = merge_default_config({})
        print_experimental_features(config)
        output = buf.getvalue()
        assert output == ""
    
    # Test with experimental features that have been released
    with io.StringIO() as buf, redirect_stdout(buf):
        config = merge_default_config(
            {"experimental": {"rtc": True, "chat_sidebar": True}}
        )
        print_experimental_features(config)
        output = buf.getvalue()
        assert output == ""
    
    # Test with experimental features that have not been released
    with io.StringIO() as buf, redirect_stdout(buf):
        config = merge_default_config(
            {"experimental": {"new_feature": True}}
        )
        print_experimental_features(config)
        output = buf.getvalue()
        assert "Experimental features" in output
        assert "new_feature" in output
