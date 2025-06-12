# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import re


def extract_missing_module_from_cause_chain(
    error: ImportError,
) -> str | None:
    """Traverse an `ImportError` cause chain maybe find a missing module name.

    This handles cases where a `ModuleNotFoundError` was raised and then wrapped,
    e.g., via `raise ImportError("helpful message") from err`
    """
    current: None | BaseException = error
    while current is not None:
        if (
            isinstance(current, ModuleNotFoundError)
            and hasattr(current, "name")
            and current.name
        ):
            return current.name
        current = current.__cause__
    return None


def extract_packages_from_pip_install_suggestion(
    message: str,
) -> list[str] | None:
    """Extract package names from pip install commands in error messages."""

    # First try to find quoted/backticked pip install commands (complete commands)
    quoted_patterns = [
        r"`pip install\s+([^`]+)`",  # backticks
        r'"pip install\s+([^"]+)"',  # double quotes
        r"'pip install\s+([^']+)'",  # single quotes
    ]

    for pattern in quoted_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            args_part = match.group(1)
            args = args_part.split()
            packages = []
            seen = set()

            for arg in args:
                # Skip flags and duplicates
                if not arg.startswith("-") and arg not in seen:
                    packages.append(arg)
                    seen.add(arg)

            if packages:
                return packages

    # If no quoted command found, look for unquoted and take only first positional arg
    unquoted_pattern = (
        r"pip install\s+([a-zA-Z0-9_-]+(?:\[[a-zA-Z0-9_,-]+\])?)"
    )
    match = re.search(unquoted_pattern, message, re.IGNORECASE)

    if match:
        return [match.group(1)]

    return None


def extract_packages_special_cases(message: str) -> list[str] | None:
    """Extract package names based on special case substrings in error messages."""

    special_cases = {
        # pd.DataFrame.to_parquet()
        "Unable to find a usable engine; tried using: 'pyarrow', 'fastparquet'.": [
            "pyarrow"
        ],
    }

    packages = []
    for substring, package_names in special_cases.items():
        if substring in message:
            packages.extend(package_names)

    return packages if packages else None


def try_extract_packages_from_import_error_message(
    import_error_message: str,
) -> list[str] | None:
    """Try to extract package names from an `ImportError` message using various strategies.

    Args:
        import_error_message: The error message

    Returns:
        List of package names if found, None otherwise
    """

    for extract in [
        extract_packages_from_pip_install_suggestion,
        extract_packages_special_cases,
    ]:
        result = extract(import_error_message)
        if result is not None:
            return result
    return None
