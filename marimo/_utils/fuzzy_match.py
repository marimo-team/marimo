# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import re


def compile_regex(query: str) -> tuple[re.Pattern[str] | None, bool]:
    """
    Returns compiled regex pattern and whether the query is a valid regex.
    """
    try:
        return re.compile(query, re.IGNORECASE), True
    except re.error:
        return None, False


def is_fuzzy_match(
    query: str,
    name: str,
    compiled_pattern: re.Pattern[str] | None,
    is_regex: bool,
) -> bool:
    """
    Fuzzy match using pre-compiled regex. If is not regex, fallback to substring match.

    Args:
        query: The query to match.
        name: The name to match against.
        compiled_pattern: Pre-compiled regex pattern (None if not regex).
        is_regex: Whether the query is a valid regex.
    """
    if is_regex and compiled_pattern:
        return bool(compiled_pattern.search(name))
    else:
        return query.lower() in name.lower()
