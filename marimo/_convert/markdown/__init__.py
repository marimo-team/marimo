# Copyright 2026 Marimo. All rights reserved.
"""Markdown conversion utilities for marimo notebooks.

This module provides bidirectional conversion between markdown and marimo IR:
- `to_ir`: Parse markdown (.md, .qmd) files into marimo notebook IR
- `from_ir`: Export marimo notebook IR to markdown format
"""

from __future__ import annotations

from marimo._convert.markdown.from_ir import convert_from_ir_to_markdown
from marimo._convert.markdown.to_ir import (
    convert_from_md_to_marimo_ir,
    extract_frontmatter,
    formatted_code_block,
    is_sanitized_markdown,
    sanitize_markdown,
)

__all__ = [
    # Export (IR → Markdown)
    "convert_from_ir_to_markdown",
    # Import (Markdown → IR)
    "convert_from_md_to_marimo_ir",
    # Utilities
    "extract_frontmatter",
    "formatted_code_block",
    "is_sanitized_markdown",
    "sanitize_markdown",
]
