# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

GENERATED_WITH_RE = re.compile(r"^__generated_with = .*$", re.MULTILINE)


def contents_differ_excluding_generated_with(
    original: str, generated: str
) -> bool:
    """Compare file contents while ignoring `__generated_with` differences."""
    return (
        GENERATED_WITH_RE.sub("", original).strip()
        != GENERATED_WITH_RE.sub("", generated).strip()
    )
