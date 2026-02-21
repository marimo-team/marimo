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

    # Matches inline RST math role: :math:`...`
    INLINE_MATH_ROLE_PATTERN = re.compile(r"(?<!`):math:`([^`\n]+)`")
    # Matches role variant with embedded HTML code tag: :math:<code>...</code>
    INLINE_MATH_ROLE_HTML_CODE_PATTERN = re.compile(
        r":math:\s*<code>(.+?)</code>",
        re.DOTALL,
    )
    # Matches display bracket delimiters: \[...\]
    DISPLAY_BRACKET_PATTERN = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
    # Matches inline paren delimiters: \(...\)
    INLINE_PAREN_PATTERN = re.compile(r"\\\((.+?)\\\)", re.DOTALL)

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)

    def run(self, lines: list[str]) -> list[str]:
        """Normalize math syntaxes before markdown parsing.

        This keeps legacy/reStructuredText math forms renderable by arithmatex
        and preserves the existing $$ block-spacing fix from #8348.
        """
        text = "\n".join(lines)
        if not self._contains_math_syntax(text):
            return lines

        text = self._normalize_math_syntax(text)
        return self._normalize_display_math_spacing(text.split("\n"))

    def _contains_math_syntax(self, text: str) -> bool:
        return (
            "$$" in text
            or ".. math::" in text
            or ":math:`" in text
            or ":math:<code>" in text
            or "\\(" in text
            or "\\[" in text
        )

    def _normalize_math_syntax(self, text: str) -> str:
        """Convert supported math delimiters in non-inline-code regions.

        Supported conversions:
        - ``:math:`...``` and ``:math:<code>...</code>`` -> ``$...$``
        - ``.. math::`` blocks -> ``$$...$$``
        - ``\\(...\\)`` -> ``$...$``
        - ``\\[...\\]`` -> ``$$...$$``
        """
        converted_segments: list[str] = []
        for segment, is_inline_code in self._split_by_inline_code(text):
            if is_inline_code:
                converted_segments.append(segment)
                continue

            segment = self.INLINE_MATH_ROLE_PATTERN.sub(
                lambda match: f"${match.group(1).strip()}$",
                segment,
            )
            segment = self.INLINE_MATH_ROLE_HTML_CODE_PATTERN.sub(
                lambda match: f"${match.group(1).strip()}$",
                segment,
            )
            segment = self._convert_rst_math_blocks(segment)
            segment = self.DISPLAY_BRACKET_PATTERN.sub(
                lambda match: self._to_display_math(match.group(1)),
                segment,
            )
            segment = self.INLINE_PAREN_PATTERN.sub(
                lambda match: f"${match.group(1).strip()}$",
                segment,
            )
            converted_segments.append(segment)

        return "".join(converted_segments)

    def _normalize_display_math_spacing(self, lines: list[str]) -> list[str]:
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

    def _split_by_inline_code(self, text: str) -> list[tuple[str, bool]]:
        """Split text into inline-code and non-code segments.

        We skip normalization in inline code segments so examples such as
        ```:math:`x``` remain literal.
        """
        segments: list[tuple[str, bool]] = []
        current: list[str] = []
        i = 0
        in_code = False
        delimiter = ""

        while i < len(text):
            char = text[i]
            if char == "`":
                # Keep ``:math:`...``` as a role token; its backticks are not
                # markdown inline-code delimiters.
                if not in_code and text[max(0, i - 6) : i] == ":math:":
                    role_end = text.find("`", i + 1)
                    if role_end != -1:
                        current.append(text[i : role_end + 1])
                        i = role_end + 1
                        continue

                j = i
                while j < len(text) and text[j] == "`":
                    j += 1
                ticks = text[i:j]

                if in_code and ticks == delimiter:
                    current.append(ticks)
                    segments.append(("".join(current), True))
                    current = []
                    in_code = False
                    delimiter = ""
                    i = j
                    continue

                if not in_code:
                    if current:
                        segments.append(("".join(current), False))
                        current = []
                    in_code = True
                    delimiter = ticks
                    current.append(ticks)
                    i = j
                    continue

            current.append(char)
            i += 1

        if current:
            segments.append(("".join(current), in_code))
        return segments

    def _convert_rst_math_blocks(self, text: str) -> str:
        """Convert ``.. math::`` directives to markdown display math blocks.

        Handles inline and multiline directive bodies, optional directive
        options, and a permissive unindented LaTeX continuation case used in
        third-party docstrings.
        """
        lines = text.splitlines()
        if not lines:
            return text

        output: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Matches RST math directive lines: ".. math:: ..."
            directive_match = re.match(r"^([ \t]*)\.\.\s+math::(.*)$", line)
            if directive_match is None:
                output.append(line)
                i += 1
                continue

            inline_math = directive_match.group(2).strip()
            base_indent = self._count_indent(line)
            i += 1

            block_lines: list[str] = []
            consume_unindented_block = bool(
                inline_math and "\\begin" in inline_math
            )
            if inline_math:
                block_lines.append(inline_math)
            else:
                while i < len(lines):
                    current_line = lines[i]
                    if not current_line.strip():
                        i += 1
                        continue

                    is_option_line = self._count_indent(
                        current_line
                    ) > base_indent and current_line.strip().startswith(":")
                    if is_option_line:
                        i += 1
                        continue
                    break

                if i < len(lines):
                    next_line = lines[i]
                    consume_unindented_block = (
                        bool(next_line.strip())
                        and self._count_indent(next_line) <= base_indent
                        and next_line.lstrip().startswith("\\")
                    )

            if consume_unindented_block:
                while i < len(lines) and lines[i].strip():
                    block_lines.append(lines[i])
                    i += 1
            else:
                while i < len(lines):
                    current_line = lines[i]
                    if not current_line.strip():
                        block_lines.append("")
                        i += 1
                        continue
                    if self._count_indent(current_line) <= base_indent:
                        break
                    block_lines.append(current_line)
                    i += 1

            if not any(math_line.strip() for math_line in block_lines):
                output.append(line)
                continue

            min_indent = min(
                self._count_indent(math_line)
                for math_line in block_lines
                if math_line.strip()
            )
            dedented_lines: list[str] = []
            for math_line in block_lines:
                if not math_line:
                    dedented_lines.append("")
                    continue
                strip_chars = min(min_indent, self._count_indent(math_line))
                dedented_lines.append(math_line[strip_chars:])

            math_body = "\n".join(dedented_lines).strip("\n")
            output.extend(("$$", math_body, "$$"))

        normalized = "\n".join(output)
        if text.endswith("\n"):
            normalized += "\n"
        return normalized

    def _count_indent(self, line: str) -> int:
        # Matches leading whitespace used to compute visual indentation.
        match = re.match(r"^[ \t]*", line)
        return len(match.group(0).expandtabs(4)) if match else 0

    def _to_display_math(self, math: str) -> str:
        math = math.strip()
        if not math:
            return ""
        return f"\n\n$$\n{math}\n$$\n\n"


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
