# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

GENERATED_WITH_RE = re.compile(r"^__generated_with = .*$", re.MULTILINE)
# Markdown notebooks record the version in frontmatter instead.
MARIMO_VERSION_RE = re.compile(r"^marimo-version: .*$", re.MULTILINE)


def _strip_version(contents: str) -> str:
    return MARIMO_VERSION_RE.sub(
        "", GENERATED_WITH_RE.sub("", contents)
    ).strip()


def contents_differ_excluding_generated_with(
    original: str, generated: str
) -> bool:
    """Compare file contents while ignoring the recorded marimo version."""
    return _strip_version(original) != _strip_version(generated)
