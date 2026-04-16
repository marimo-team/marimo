# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

import marimo._cli.print as cli_print
from marimo._cli.tips import CliTip
from marimo._config.config import merge_default_config
from marimo._server.print import (
    _colorized_url,
    _format_startup_tip,
    _get_network_url,
    _utf8,
    print_experimental_features,
    print_shutdown,
    print_startup,
)


@pytest.fixture(autouse=True)
def _disable_cli_style() -> None:
    with patch.object(cli_print, "_style", cli_print._noop_style):
        yield


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

    # Test with an IPv6 address (RFC 3986 requires brackets)
    result = _colorized_url("http://[2001:db8::1]:8000/path")
    assert "[2001:db8::1]:8000/path" in result

    # Test with IPv6 loopback
    result = _colorized_url("http://[::1]:2718")
    assert "[::1]:2718" in result

    # Zone IDs must not appear in URLs (stripped before URL construction)
    result = _colorized_url("http://[fe80::1]:2718")
    assert "[fe80::1]:2718" in result
    assert "%" not in result


def test_get_network_url() -> None:
    """Test the _get_network_url function."""
    # Test with a simple URL using socket connection method
    with patch("socket.socket") as mock_socket:
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.getsockname.return_value = ("192.168.1.100", 0)
        result = _get_network_url("http://localhost:8000")
        assert result == "http://192.168.1.100:8000"

    # Test with socket connection failing, falling back to getaddrinfo
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.connect.side_effect = Exception(
            "Test exception"
        )
        with patch("socket.gethostname") as mock_gethostname:
            mock_gethostname.return_value = "test-host"
            with patch("socket.getaddrinfo") as mock_getaddrinfo:
                mock_getaddrinfo.return_value = [
                    (2, 1, 6, "", ("192.168.1.100", 0)),
                    (2, 1, 6, "", ("127.0.0.1", 0)),
                ]
                result = _get_network_url("http://localhost:8000")
                assert result == "http://192.168.1.100:8000"

    # Test with both socket and getaddrinfo failing
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.connect.side_effect = Exception(
            "Test exception"
        )
        with patch("socket.gethostname") as mock_gethostname:
            mock_gethostname.return_value = "test-host"
            with patch("socket.getaddrinfo") as mock_getaddrinfo:
                mock_getaddrinfo.side_effect = Exception("Test exception")
                result = _get_network_url("http://localhost:8000")
                assert result == "http://test-host:8000"


def test_format_startup_tip_with_command() -> None:
    tip = CliTip(
        text="Install shell completions",
        command="marimo shell-completion",
    )
    summary, action = _format_startup_tip(tip)
    assert "Tip: Install shell completions" in summary
    assert action == "$ marimo shell-completion"


def test_format_startup_tip_with_link() -> None:
    tip = CliTip(
        text="Coming from Jupyter?",
        link="https://docs.marimo.io/guides/coming_from/jupyter/",
    )
    summary, action = _format_startup_tip(tip)
    assert "Tip: Coming from Jupyter?" in summary
    assert action == (
        "Guide: https://docs.marimo.io/guides/coming_from/jupyter/"
    )


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
    with (
        io.StringIO() as buf,
        redirect_stdout(buf),
        patch("marimo._server.print._get_network_url") as mock_get_network_url,
    ):
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
    with (
        io.StringIO() as buf,
        redirect_stdout(buf),
        patch("marimo._server.print._get_network_url") as mock_get_network_url,
    ):
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


def test_print_startup_prints_tip_after_url() -> None:
    tip = CliTip(
        text="Open the intro tutorial",
        command="marimo tutorial intro",
    )
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name=None,
            url="http://localhost:8000",
            run=False,
            new=False,
            network=False,
            startup_tip=tip,
        )
        output = buf.getvalue()
        assert "Tip: Open the intro tutorial" in output
        assert "$ marimo tutorial intro" in output
        assert "localhost:8000\n\n        " in output
        assert output.index("URL") < output.index(
            "Tip: Open the intro tutorial"
        )
        assert output.index("Tip: Open the intro tutorial") < output.index(
            "$ marimo tutorial intro"
        )


def test_print_startup_prints_tip_after_network() -> None:
    tip = CliTip(
        text="Run a notebook as a web app",
        command="marimo run notebook.py",
    )
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch(
            "marimo._server.print._get_network_url"
        ) as mock_get_network_url:
            mock_get_network_url.return_value = "http://192.168.1.100:8000"
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=True,
                startup_tip=tip,
            )
        output = buf.getvalue()
        assert "Tip: Run a notebook as a web app" in output
        assert "$ marimo run notebook.py" in output
        assert "192.168.1.100:8000\n\n        " in output
        assert output.index("URL") < output.index("Network")
        assert output.index("Network") < output.index(
            "Tip: Run a notebook as a web app"
        )


def test_print_startup_omits_tip_when_none() -> None:
    with io.StringIO() as buf, redirect_stdout(buf):
        print_startup(
            file_name=None,
            url="http://localhost:8000",
            run=False,
            new=False,
            network=False,
            startup_tip=None,
        )
        output = buf.getvalue()
        assert "Tip:" not in output


def test_print_startup_utf8_tip_fallback_omits_emoji() -> None:
    tip = CliTip(
        text="Install shell completions",
        command="marimo shell-completion",
    )
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch("marimo._server.print.UTF8_SUPPORTED", False):
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=False,
                startup_tip=tip,
            )
        output = buf.getvalue()
        assert "Tip: Install shell completions" in output
        assert "$ marimo shell-completion" in output
        assert "💡" not in output


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
        config = merge_default_config({"experimental": {"new_feature": True}})
        print_experimental_features(config)
        output = buf.getvalue()
        assert "Experimental features" in output
        assert "new_feature" in output
