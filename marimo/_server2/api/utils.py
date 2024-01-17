from __future__ import annotations

import os

from altair import Optional


def require_header(header: list[str] | None) -> str:
    """
    Require exactly one value in header and return it.
    """

    if header is None:
        raise ValueError("Expected exactly one value in header, got None")
    if len(header) != 1:
        raise ValueError(
            f"Expected exactly one value in header, got {len(header)} values: {header}"
        )
    return header[0]


def parse_title(filename: Optional[str]) -> str:
    """
    Parse a filename into a (name, extension) tuple.
    """
    if filename is None:
        return "marimo"

    # filename is used as title, except basename and suffix are
    # stripped and underscores are replaced with spaces
    return os.path.splitext(os.path.basename(filename))[0].replace("_", " ")
