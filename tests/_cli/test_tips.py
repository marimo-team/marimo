# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
from unittest.mock import patch

from marimo._cli import cli
from marimo._cli.tips import (
    CLI_STARTUP_TIPS,
    CliTip,
    choose_startup_tip,
    get_relevant_startup_tips,
    signature_from_click_context,
    signature_from_command_example,
)


def _make_subcommand_context(args: list[str]):
    root = cli.main.make_context("marimo", args, resilient_parsing=True)
    cmd_name, cmd, rest = cli.main.resolve_command(root, list(args))
    return cmd.make_context(
        cmd_name, rest, parent=root, resilient_parsing=True
    )


def test_signature_from_click_context_edit_watch() -> None:
    ctx = _make_subcommand_context(["edit", "notebook.py", "--watch"])
    signature = signature_from_click_context(ctx)
    assert signature.command_path == ("edit",)
    assert signature.enabled_options == frozenset({"watch"})


def test_signature_from_click_context_root_option_with_value() -> None:
    ctx = _make_subcommand_context(
        ["--log-level", "INFO", "edit", "notebook.py", "--watch"]
    )
    signature = signature_from_click_context(ctx)
    assert signature.command_path == ("edit",)
    assert signature.enabled_options == frozenset({"log_level", "watch"})


def test_signature_from_click_context_ignores_negated_boolean_flag() -> None:
    ctx = _make_subcommand_context(["edit", "notebook.py", "--no-sandbox"])
    signature = signature_from_click_context(ctx)
    assert signature.command_path == ("edit",)
    assert signature.enabled_options == frozenset()


def test_signature_from_command_example_edit_watch() -> None:
    signature = signature_from_command_example(
        cli.main, "marimo edit notebook.py --watch"
    )
    assert signature is not None
    assert signature.command_path == ("edit",)
    assert signature.enabled_options == frozenset({"watch"})


def test_signature_from_command_example_edit_sandbox() -> None:
    signature = signature_from_command_example(
        cli.main, "marimo edit --sandbox notebook.py"
    )
    assert signature is not None
    assert signature.command_path == ("edit",)
    assert signature.enabled_options == frozenset({"sandbox"})


def test_signature_from_command_example_run() -> None:
    signature = signature_from_command_example(
        cli.main, "marimo run notebook.py"
    )
    assert signature is not None
    assert signature.command_path == ("run",)
    assert signature.enabled_options == frozenset()


def test_signature_from_command_example_fails_open() -> None:
    assert (
        signature_from_command_example(cli.main, 'marimo run "unterminated')
        is None
    )


def test_get_relevant_startup_tips_skips_redundant_watch_tip() -> None:
    current = signature_from_click_context(
        _make_subcommand_context(["edit", "notebook.py", "--watch"])
    )
    filtered = get_relevant_startup_tips(CLI_STARTUP_TIPS, current, cli.main)
    assert all(
        tip.command != "marimo edit notebook.py --watch" for tip in filtered
    )


def test_get_relevant_startup_tips_keeps_watch_tip_without_watch() -> None:
    current = signature_from_click_context(
        _make_subcommand_context(["edit", "notebook.py"])
    )
    filtered = get_relevant_startup_tips(CLI_STARTUP_TIPS, current, cli.main)
    assert any(
        tip.command == "marimo edit notebook.py --watch" for tip in filtered
    )


def test_get_relevant_startup_tips_keeps_sandbox_tip_with_no_sandbox() -> None:
    current = signature_from_click_context(
        _make_subcommand_context(["edit", "notebook.py", "--no-sandbox"])
    )
    filtered = get_relevant_startup_tips(CLI_STARTUP_TIPS, current, cli.main)
    assert any(
        tip.command == "marimo edit --sandbox notebook.py" for tip in filtered
    )


def test_get_relevant_startup_tips_skips_redundant_run_tip() -> None:
    current = signature_from_click_context(
        _make_subcommand_context(["run", "notebook.py"])
    )
    filtered = get_relevant_startup_tips(CLI_STARTUP_TIPS, current, cli.main)
    assert all(tip.command != "marimo run notebook.py" for tip in filtered)


def test_choose_startup_tip_tty_only() -> None:
    ctx = _make_subcommand_context(["edit", "notebook.py"])
    with patch("marimo._cli.tips.sys.stdout", new=io.StringIO()):
        assert choose_startup_tip(ctx) is None


def test_choose_startup_tip_uses_filtered_pool() -> None:
    class TTYStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    ctx = _make_subcommand_context(["edit", "notebook.py", "--watch"])
    with patch("marimo._cli.tips.sys.stdout", new=TTYStringIO()):
        with patch("marimo._cli.tips.random.choice") as mock_choice:
            mock_choice.return_value = CliTip(text="x")
            choose_startup_tip(ctx)
            pool = mock_choice.call_args.args[0]
            assert all(
                tip.command != "marimo edit notebook.py --watch"
                for tip in pool
            )
