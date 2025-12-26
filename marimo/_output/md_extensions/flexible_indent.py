# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

from markdown import Extension, Markdown, preprocessors  # type: ignore


class FlexibleIndentPreprocessor(preprocessors.Preprocessor):  # type: ignore[misc]
    """
    Preprocessor to standardize list indentation to specific levels.
    Normalizes inconsistent indentation to match the allowed levels.
    """

    # Pattern to match lines that start list items (ordered or unordered)
    # Captures: (indentation, list_marker, trailing_space, content)
    LIST_PATTERN = re.compile(r"^(\s*)([*+-]|\d+\.)(\s+)(.*)$", re.MULTILINE)
    INDENT_LEVELS = [2, 4]
    BASE_INDENT_SIZE = 4
    FOUR_SPACES = "    "

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)

    def _detect_base_indent(self, lines: list[str]) -> int:
        """
        Detect the base indentation level used in the document.

        Returns 2 for 2-space indentation or 4 for 4-space indentation.
        """
        indents: list[int] = []
        for line in lines:
            match = self.LIST_PATTERN.match(line)
            if match:
                indent_str = match.group(1)
                if indent_str:  # Skip non-indented items
                    indent_count = len(
                        indent_str.replace("\t", self.FOUR_SPACES)
                    )
                    indents.append(indent_count)

        if not indents:
            return self.BASE_INDENT_SIZE

        # Find the smallest non-zero indent - this is likely our base level
        min_indent = min(indents)

        # Choose the closest allowed indent level
        if min_indent <= 2:
            return 2
        else:
            return self.BASE_INDENT_SIZE

    def _normalize_indentation(self, indent_str: str, base_level: int) -> str:
        """
        Normalize indentation to consistent 2-space increments.

        This ensures that both 2-space and 4-space indentation patterns
        result in the same normalized output.

        Args:
            indent_str: The original indentation string
            base_level: The detected base indentation level (2 or 4)

        Returns:
            Normalized indentation string using 2-space increments
        """
        # Convert tabs to spaces (assuming 1 tab = 4 spaces)
        normalized = indent_str.replace("\t", self.FOUR_SPACES)
        indent_count = len(normalized)

        if indent_count == 0:
            return ""

        # Calculate the intended nesting level based on the base level
        nesting_level = max(1, round(indent_count / base_level))

        # Always output using 4-space increments since that is what the markdown spec requires
        return " " * (4 * nesting_level)

    def _get_list_depth(self, indent_str: str, base_level: int = 2) -> int:
        """Calculate the nesting depth of a list item."""
        normalized = indent_str.replace("\t", self.FOUR_SPACES)
        indent_count = len(normalized)

        if indent_count == 0:
            return 0

        # Calculate depth based on the base level
        return max(1, round(indent_count / base_level))

    def run(self, lines: list[str]) -> list[str]:
        """Process the lines and normalize list indentation."""
        if not lines:
            return lines

        # Detect the base indentation level used in this document
        base_level = self._detect_base_indent(lines)

        result_lines: list[str] = []

        for line in lines:
            match = self.LIST_PATTERN.match(line)
            if match:
                indent, marker, space, content = match.groups()

                # Normalize the indentation based on detected base level
                normalized_indent = self._normalize_indentation(
                    indent, base_level
                )

                # Reconstruct the line with normalized indentation
                normalized_line = (
                    f"{normalized_indent}{marker}{space}{content}"
                )
                result_lines.append(normalized_line)
            else:
                result_lines.append(line)

        return result_lines


class FlexibleIndentExtension(Extension):  # type: ignore[misc]
    """
    Extension to provide flexible list indentation support.
    """

    def extendMarkdown(self, md: Markdown) -> None:
        """Add the preprocessor to the markdown instance."""
        # Register preprocessor to normalize indentation
        md.preprocessors.register(
            FlexibleIndentPreprocessor(md),
            "flexible_indent",
            # Run early, before breakless_lists and other list processing
            35,
        )
