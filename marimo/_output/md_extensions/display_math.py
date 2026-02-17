# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

from markdown import Extension, Markdown, preprocessors  # type: ignore


class DisplayMathPreprocessor(preprocessors.Preprocessor):  # type: ignore[misc]
    """
    Ensures $$...$$ display math blocks are surrounded by blank lines.

    The pymdownx.arithmatex block processor requires $$...$$ to be in its
    own markdown "block" (between blank lines) to recognize it as display
    math. Without blank lines, it either produces nested tags with inline
    delimiters or fails entirely.

    This preprocessor inserts blank lines around $$...$$ blocks so that
    arithmatex always processes them as display math.
    """

    # Single-line display math: $$...$$  on its own line
    SINGLE_LINE_PATTERN = re.compile(r"^\s*\$\$(.+)\$\$\s*$")

    # Opening or closing $$ on its own line
    DOLLAR_DOLLAR_PATTERN = re.compile(r"^\s*\$\$\s*$")

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)

    def run(self, lines: list[str]) -> list[str]:
        # Fast path: skip processing if no $$ appears anywhere
        if not any("$$" in line for line in lines):
            return lines

        result: list[str] = []
        i = 0
        in_multiline = False

        while i < len(lines):
            line = lines[i]

            if in_multiline:
                # Looking for closing $$
                if self.DOLLAR_DOLLAR_PATTERN.match(line):
                    result.append(line)
                    # Add blank line after closing $$ if next line is non-empty
                    if i + 1 < len(lines) and lines[i + 1].strip() != "":
                        result.append("")
                    in_multiline = False
                else:
                    result.append(line)
            elif self.SINGLE_LINE_PATTERN.match(line):
                # Single-line $$...$$ — add blank lines around it
                if result and result[-1].strip() != "":
                    result.append("")
                result.append(line)
                if i + 1 < len(lines) and lines[i + 1].strip() != "":
                    result.append("")
            elif self.DOLLAR_DOLLAR_PATTERN.match(line):
                # Opening $$ of a multi-line block
                if result and result[-1].strip() != "":
                    result.append("")
                result.append(line)
                in_multiline = True
            else:
                result.append(line)

            i += 1

        return result


class DisplayMathExtension(Extension):  # type: ignore[misc]
    """
    Extension to ensure $$...$$ display math renders correctly
    without requiring surrounding blank lines.
    """

    def extendMarkdown(self, md: Markdown) -> None:
        md.preprocessors.register(
            DisplayMathPreprocessor(md),
            "display_math_preproc",
            # Priority 24: runs AFTER fenced_code_block/superfences (25)
            # which stash code blocks as tokens, so we never modify
            # $$ inside code fences.
            24,
        )
