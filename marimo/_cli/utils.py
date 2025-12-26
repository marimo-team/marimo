# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from pathlib import Path
from sys import stdout
from typing import Optional

import click

from marimo import _loggers
from marimo._ast.load import get_notebook_status
from marimo._ast.parse import MarimoFileError
from marimo._cli.print import bold, green
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.tokens import AuthToken


def prompt_to_overwrite(path: Path) -> bool:
    if GLOBAL_SETTINGS.YES:
        return True

    # Check if not in an interactive terminal
    # default to False
    if not stdout.isatty():
        return True

    if path.exists():
        return click.confirm(
            f"Warning: The file '{path}' already exists. Overwrite?",
            default=False,
        )

    return True


def resolve_token(
    token: bool,
    *,
    token_password: Optional[str],
    token_password_file: Optional[str],
) -> Optional[AuthToken]:
    token_password = resolve_token_password(
        token_password=token_password,
        token_password_file=token_password_file,
    )
    if token_password:
        return AuthToken(token_password)
    elif token is False:
        # Empty means no auth
        return AuthToken("")
    # None means use the default (generated) token
    return None


def resolve_token_password(
    token_password: Optional[str],
    token_password_file: Optional[str],
) -> Optional[str]:
    """
    Resolve token password from mutually exclusive sources.

    Args:
        token_password: Direct password string (legacy)
        token_password_file: Path to file containing password, or '-' for stdin

    Returns:
        The resolved password string, or None if no password source provided

    Raises:
        click.UsageError: If multiple password sources are provided
    """
    # Enforce mutual exclusivity
    if token_password is not None and token_password_file is not None:
        raise click.UsageError(
            "Only one of --token-password or --token-password-file may be specified."
        )

    # Direct password (existing behavior)
    if token_password:
        return token_password

    # Read from file or stdin
    if token_password_file:
        password: str
        try:
            # Handle stdin special case
            if token_password_file == "-":
                if sys.stdin.isatty():
                    password = click.prompt(
                        "Enter token password", hide_input=True
                    )
                else:
                    password = sys.stdin.read().strip()
                if not password:
                    raise click.UsageError(
                        "No token password provided on stdin"
                    )
                return password

            # Read from file
            with open(token_password_file, encoding="utf-8") as f:
                password = f.read().strip()
                if not password:
                    raise click.UsageError(
                        f"No token password found in file: {token_password_file}"
                    )
                return password
        except click.UsageError:
            # Re-raise our own usage errors
            raise
        except FileNotFoundError:
            raise click.UsageError(
                f"Token password file not found: {token_password_file}"
            ) from None
        except PermissionError:
            raise click.UsageError(
                f"Permission denied reading token password file: {token_password_file}"
            ) from None
        except Exception as e:
            raise click.UsageError(
                f"Error reading token password from file: {e}"
            ) from None

    # No password source provided
    return None


def check_app_correctness(filename: str, noninteractive: bool = True) -> None:
    try:
        status = get_notebook_status(filename).status
    except (SyntaxError, MarimoFileError):
        # Exit early if we can
        if not noninteractive:
            raise

        # This prints a more readable error message, without internal details
        # e.g.
        # Error:   File "/my/bad/file.py", line 17
        #     x.
        #     ^
        # SyntaxError: invalid syntax
        from marimo._lint import collect_messages

        _, message = collect_messages(filename)
        raise click.ClickException(message.strip()) from None

    if status == "invalid" and filename.endswith(".py"):
        # fail for python scripts, almost certainly do not want to override contents
        import os

        stem = os.path.splitext(os.path.basename(filename))[0]
        raise click.ClickException(
            f"Python script not recognized as a marimo notebook.\n\n"
            f"  {green('Tip:')} Try converting with"
            "\n\n"
            f"    marimo convert {filename} -o {stem}_nb.py\n\n"
            f"  then open with marimo edit {stem}_nb.py"
        ) from None

    # Only show the tip if we're in an interactive terminal
    interactive = sys.stdin.isatty() and not noninteractive
    if status == "invalid" and interactive:
        click.echo(
            green("tip")
            + ": Use `"
            + bold("marimo convert")
            + "` to convert existing scripts.",
            err=True,
        )
        click.confirm(
            (
                "The file is not detected as a marimo notebook, opening it may "
                "overwrite its contents.\nDo you want to open it anyway?"
            ),
            default=False,
            abort=True,
        )

    if status == "has_errors":
        # Provide a warning, but allow the user to open the notebook
        _loggers.marimo_logger().warning(
            "This notebook has errors, saving may lose data. Continuing anyway."
        )


def check_app_correctness_or_convert(filename: str) -> None:
    from marimo._convert.converters import MarimoConvert

    file = Path(filename)
    code = file.read_text(encoding="utf-8")
    try:
        return check_app_correctness(filename, noninteractive=True)
    except (click.ClickException, MarimoFileError):
        # A click exception is raised if a python script could not be converted
        code = MarimoConvert.from_non_marimo_python_script(
            source=code, aggressive=True
        ).to_py()
    except SyntaxError:
        # The file could not even be read as python
        code = MarimoConvert.from_plain_text(source=code).to_py()
        file.write_text(code, encoding="utf-8")

    file.write_text(code, encoding="utf-8")
