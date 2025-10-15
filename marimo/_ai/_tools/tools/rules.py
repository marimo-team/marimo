# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import marimo._utils.requests as requests
from marimo import _loggers
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import EmptyArgs, SuccessResult, ToolGuidelines

LOGGER = _loggers.marimo_logger()

# We load the rules remotely, so we can update these without requiring a new release.
# If requested, we can bundle this into the library instead.
MARIMO_RULES_URL = "https://docs.marimo.io/CLAUDE.md"


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
