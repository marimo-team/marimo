# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import marimo._utils.requests as requests
from marimo import _loggers
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import EmptyArgs, SuccessResult, ToolGuidelines
from marimo._utils.paths import marimo_package_path

LOGGER = _loggers.marimo_logger()

# We ship the rules with the package in _static/CLAUDE.md
# If the file doesn't exist (development or edge cases), we fallback to fetching from the URL
MARIMO_RULES_URL = "https://docs.marimo.io/CLAUDE.md"
MARIMO_RULES_PATH = marimo_package_path() / "_static" / "CLAUDE.md"


@dataclass
class GetMarimoRulesOutput(SuccessResult):
    rules_content: Optional[str] = None
    source_url: str = MARIMO_RULES_URL


class GetMarimoRules(ToolBase[EmptyArgs, GetMarimoRulesOutput]):
    """Get the official marimo rules and guidelines for AI assistants.

    Returns:
        The content of the rules file.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "Before using other marimo mcp tools, reading a marimo notebook, or writing to a notebook ALWAYS use this first to understand how marimo works",
        ],
        avoid_if=[
            "The rules have already been retrieved recently, as they rarely change",
        ],
    )

    def handle(self, args: EmptyArgs) -> GetMarimoRulesOutput:
        del args

        # First, try to load from the bundled file
        if MARIMO_RULES_PATH.exists():
            try:
                rules_content = MARIMO_RULES_PATH.read_text(encoding="utf-8")
                return GetMarimoRulesOutput(
                    rules_content=rules_content,
                    source_url="bundled",
                    next_steps=[
                        "Follow the guidelines in the rules when working with marimo notebooks",
                    ],
                )
            except Exception as e:
                LOGGER.warning(
                    "Failed to read bundled marimo rules from %s: %s",
                    MARIMO_RULES_PATH,
                    str(e),
                )
                # Fall through to fetch from URL

        # Fallback: fetch from the URL
        try:
            response = requests.get(MARIMO_RULES_URL, timeout=10)
            response.raise_for_status()

            return GetMarimoRulesOutput(
                rules_content=response.text(),
                source_url=MARIMO_RULES_URL,
                next_steps=[
                    "Follow the guidelines in the rules when working with marimo notebooks",
                ],
            )

        except Exception as e:
            LOGGER.warning(
                "Failed to fetch marimo rules from %s: %s",
                MARIMO_RULES_URL,
                str(e),
            )

            return GetMarimoRulesOutput(
                status="error",
                message=f"Failed to fetch marimo rules: {str(e)}",
                source_url=MARIMO_RULES_URL,
                next_steps=[
                    "Check internet connectivity",
                    "Verify the rules URL is accessible",
                    "Try again later if the service is temporarily unavailable",
                ],
            )
