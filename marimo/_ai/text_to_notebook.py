# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from marimo import __version__
from marimo._cli.print import bold, green, muted
from marimo._config.cli_state import (
    get_cli_state,
    write_cli_state,
)
from marimo._server.utils import print_

TERMS = """
Before using marimo's Text-To-Notebook AI feature, you must accept the following terms:

1. Your prompt will be sent to marimo's API at `https://ai.marimo.app/`
2. The API uses OpenAI/Anthropic's models to convert your prompt into a notebook
3. Your prompt is securely stored for caching and service improvement purposes
4. No personal data beyond the prompt itself is collected
5. You can revoke consent at any time by modifying ~/.marimo/state.toml
"""

TERMS_LAST_UPDATED = datetime.datetime(2025, 4, 1)


def text_to_notebook(prompt: str) -> str:
    """
    Generate a notebook from a text prompt.

    Args:
        prompt: The text prompt to generate a notebook from.

    Returns:
        The generated notebook as a string.

    Raises:
        ValueError: If the user has not accepted the terms.
        RuntimeError: If the API request fails.
    """
    # Check if the user has accepted the terms
    state = get_cli_state()
    if not state:
        raise RuntimeError(
            "Failed to get CLI configuration at ~/.marimo/state.toml"
        )

    if _should_show_terms(state.accepted_text_to_notebook_terms_at):
        # User hasn't accepted terms
        print_(bold(TERMS))
        print_(bold("Do you accept these terms? (y/n)"))

        response = input().strip().lower()
        if response != "y":
            raise ValueError("Terms not accepted.")

        # Update state with acceptance
        today = datetime.datetime.now().date().strftime("%Y-%m-%d")
        state.accepted_text_to_notebook_terms_at = today

        write_cli_state(state)

    # Call the API
    try:
        url = f"https://ai.marimo.app/api/notebook.py?prompt={urllib.parse.quote(prompt)}"
        print_(muted("Generating notebook this may take a few seconds..."))

        # Create a request with a proper User-Agent header
        headers = {"User-Agent": f"marimo-cli/{__version__}"}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req) as response:
            result = response.read().decode()

        print_(green("Notebook generated successfully."))

        # Check if the response is valid
        if "marimo.App" not in result:
            raise RuntimeError(
                "Invalid response from API: missing 'marimo.App' key"
            )

        return result

    except Exception as e:
        raise RuntimeError(f"Failed to generate notebook: {str(e)}") from e


def _should_show_terms(last_accepted_at: Optional[str]) -> bool:
    """
    Determine if the terms should be shown to the user.

    Args:
        last_accepted_at (Optional[str]): The date the user last accepted the terms.

    Returns:
        bool: Whether the terms should be shown to the user.
    """
    if not last_accepted_at:
        return True
    last_accepted_date = datetime.datetime.strptime(
        last_accepted_at, "%Y-%m-%d"
    )
    return last_accepted_date < TERMS_LAST_UPDATED
