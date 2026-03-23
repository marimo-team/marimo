# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from contextlib import redirect_stdout
from unittest.mock import patch

from marimo._cli.tips import (
    CLI_STARTUP_TIPS,
    CliTip,
    StartupTipContext,
    get_relevant_startup_tips,
)
from marimo._config.config import merge_default_config
from marimo._server.print import (
    _colorized_url,
    _format_startup_tip,
    _get_network_url,
    _get_startup_tip,
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


def test_get_startup_tip_returns_none_without_tty() -> None:
    with patch("marimo._server.print.sys.stdout", new=io.StringIO()):
        assert _get_startup_tip() is None


def test_get_startup_tip_returns_random_tip_with_tty() -> None:
    class TTYStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    with patch("marimo._server.print.sys.stdout", new=TTYStringIO()):
        with patch("marimo._server.print.random.choice") as mock_choice:
            mock_choice.return_value = CLI_STARTUP_TIPS[0]
            assert _get_startup_tip() == CLI_STARTUP_TIPS[0]
            mock_choice.assert_called_once()


def test_get_relevant_startup_tips_skips_redundant_watch_tip() -> None:
    filtered = get_relevant_startup_tips(
        CLI_STARTUP_TIPS,
        StartupTipContext.from_argv(
            [
                "edit",
                "--headless",
                "marimo/_tutorials/intro.py",
                "--watch",
            ]
        ),
    )
    assert all(
        tip.command != "marimo edit notebook.py --watch" for tip in filtered
    )
    assert any(tip.command == "marimo shell-completion" for tip in filtered)


def test_get_relevant_startup_tips_skips_redundant_run_tip() -> None:
    filtered = get_relevant_startup_tips(
        CLI_STARTUP_TIPS,
        StartupTipContext.from_argv(["run", "notebook.py"]),
    )
    assert all(tip.command != "marimo run notebook.py" for tip in filtered)


def test_get_relevant_startup_tips_skips_redundant_tutorial_tip() -> None:
    filtered = get_relevant_startup_tips(
        CLI_STARTUP_TIPS,
        StartupTipContext.from_argv(["tutorial", "intro"]),
    )
    assert all(tip.command != "marimo tutorial intro" for tip in filtered)


def test_get_relevant_startup_tips_skips_redundant_sandbox_tip() -> None:
    filtered = get_relevant_startup_tips(
        CLI_STARTUP_TIPS,
        StartupTipContext.from_argv(["edit", "--sandbox", "notebook.py"]),
    )
    assert all(
        tip.command != "marimo edit --sandbox notebook.py" for tip in filtered
    )


def test_startup_tip_context_ignores_args_after_separator() -> None:
    context = StartupTipContext.from_argv(
        ["run", "notebook.py", "--", "--watch"]
    )
    assert context.command_path == ("run",)
    assert "--watch" not in context.active_flags


def test_startup_tip_context_skips_leading_global_flags() -> None:
    context = StartupTipContext.from_argv(
        ["--quiet", "--yes", "edit", "notebook.py", "--watch"]
    )
    assert context.command_path == ("edit",)
    assert "--watch" in context.active_flags


def test_get_startup_tip_uses_filtered_pool() -> None:
    class TTYStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    with patch("marimo._server.print.sys.stdout", new=TTYStringIO()):
        with patch(
            "marimo._server.print.sys.argv",
            ["marimo", "edit", "--watch"],
        ):
            with patch("marimo._server.print.random.choice") as mock_choice:
                mock_choice.return_value = CLI_STARTUP_TIPS[0]
                _get_startup_tip()
                filtered_pool = mock_choice.call_args.args[0]
                assert all(
                    tip.command != "marimo edit notebook.py --watch"
                    for tip in filtered_pool
                )


def test_get_relevant_startup_tips_ignores_malformed_tip_command() -> None:
    malformed_tip = CliTip(text="Broken", command='marimo run "unterminated')
    filtered = get_relevant_startup_tips(
        (malformed_tip,),
        StartupTipContext.from_argv(["run", "notebook.py"]),
    )
    assert filtered == (malformed_tip,)


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
            )
            output = buf.getvalue()
            assert "Create or edit notebooks" in output
            assert "URL" in output
            assert "localhost:8000" in output
            assert "Network" in output
            assert "192.168.1.100:8000" in output
            mock_get_network_url.assert_called_once_with(
                "http://localhost:8000"
            )

    # Test with network=True and _get_network_url raising an exception
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch(
            "marimo._server.print._get_network_url"
        ) as mock_get_network_url:
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
            mock_get_network_url.assert_called_once_with(
                "http://localhost:8000"
            )


def test_print_startup_prints_tip_after_url() -> None:
    tip = CliTip(
        text="Open the intro tutorial",
        command="marimo tutorial intro",
    )
    with io.StringIO() as buf, redirect_stdout(buf):
        with patch("marimo._server.print._get_startup_tip", return_value=tip):
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=False,
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
            with patch(
                "marimo._server.print._get_startup_tip",
                return_value=tip,
            ):
                print_startup(
                    file_name=None,
                    url="http://localhost:8000",
                    run=False,
                    new=False,
                    network=True,
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
        with patch("marimo._server.print._get_startup_tip", return_value=None):
            print_startup(
                file_name=None,
                url="http://localhost:8000",
                run=False,
                new=False,
                network=False,
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
            with patch(
                "marimo._server.print._get_startup_tip", return_value=tip
            ):
                print_startup(
                    file_name=None,
                    url="http://localhost:8000",
                    run=False,
                    new=False,
                    network=False,
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
