# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import re


def standardize_annotation_quotes(annotation: str) -> str:
    """Standardize quotes in type annotations to use double quotes.

    This handles complex cases like Literal['foo', 'bar'] -> Literal["foo", "bar"]
    while preserving mixed quote scenarios where double quotes are already present.

    Args:
        annotation: The type annotation string to standardize

    Returns:
        The annotation string with standardized double quotes

    Examples:
        >>> standardize_annotation_quotes("Literal['foo', 'bar']")
        'Literal["foo", "bar"]'
        >>> standardize_annotation_quotes("Literal['say \"hello\"']")
        'Literal[\'say "hello"\']'  # Preserved due to internal double quotes
        >>> standardize_annotation_quotes("int")
        'int'  # No quotes to standardize
    """

    # Regex pattern to match string literals within the annotation:
    #
    # '([^'\\]*(?:\\.[^'\\]*)*)'  - Matches single-quoted strings:
    #   - '                       - Opening single quote
    #   - ([^'\\]*                - Capture group: any chars except ' and \
    #   - (?:\\.[^'\\]*)*         - Non-capturing group: escaped char followed by non-quote/backslash chars, repeated
    #   - )'                      - Closing single quote and end capture group
    #
    # |                           - OR operator
    #
    # "([^"\\]*(?:\\.[^"\\]*)*)"  - Matches double-quoted strings:
    #   - "                       - Opening double quote
    #   - ([^"\\]*                - Capture group: any chars except " and \
    #   - (?:\\.[^"\\]*)*         - Non-capturing group: escaped char followed by non-quote/backslash chars, repeated
    #   - )"                      - Closing double quote and end capture group
    #
    # This pattern correctly handles escaped quotes within strings like 'it\'s' or "say \"hello\""
    string_pattern = (
        r"'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\""
    )

    def replace_quotes(match: re.Match[str]) -> str:
        if match.group(1) is not None:  # Single quoted string matched
            content = match.group(1)
            # Check if the content contains unescaped double quotes
            # If so, keep as single quotes to avoid escaping issues
            if '"' in content and '\\"' not in content:
                return match.group(0)  # Keep original single-quoted string
            else:
                # Convert to double quotes, handling escaped characters properly
                content = content.replace("\\'", "'")  # Unescape single quotes
                content = content.replace(
                    '"', '\\"'
                )  # Escape any double quotes
                return f'"{content}"'
        else:  # Double quoted string matched (group 2)
            return match.group(0)  # Keep as is - already using double quotes

    return re.sub(string_pattern, replace_quotes, annotation)
