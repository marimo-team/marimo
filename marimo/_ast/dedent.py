# Copyright 2026 Marimo. All rights reserved.
"""Token-aware dedent that preserves multiline string literal whitespace."""

from __future__ import annotations

import io
import re
import textwrap
import tokenize
from tokenize import TokenError

_NEWLINE_RE = re.compile(r"\r\n|\r|\n")


def split_source_lines(text: str, keepends: bool = False) -> list[str]:
    """Split source into lines the way `ast`/`tokenize` count them.

    Unlike `str.splitlines()`, this only treats `\n`, `\r`, and `\r\n` as
    line breaks. `str.splitlines()` additionally splits on `\f`, `\v`, the
    `\x1c`-`\x1e` separators, and Unicode line separators.

    When `keepends` is `True`, line terminators are preserved on each line so
    that `"".join(...)` reconstructs `text` exactly. The element count matches
    the `keepends=False` result, so the two can be indexed against each other.
    """
    if not keepends:
        return _NEWLINE_RE.sub("\n", text).split("\n")

    lines: list[str] = []
    start = 0
    for match in _NEWLINE_RE.finditer(text):
        lines.append(text[start : match.end()])
        start = match.end()
    lines.append(text[start:])
    return lines


def _get_protected_lines(
    code: str, tokens: list[tokenize.TokenInfo]
) -> list[bool]:
    """Return a bool list marking lines inside multiline string literals.

    Handles both regular triple-quoted strings (STRING token) and f-strings
    (FSTRING_START/FSTRING_MIDDLE/FSTRING_END tokens in Python 3.12+).
    """
    lines = split_source_lines(code)
    n = len(lines)
    protected = [False] * n

    # Token type values for f-string tokens (Python 3.12+)
    FSTRING_START = getattr(tokenize, "FSTRING_START", None)
    FSTRING_END = getattr(tokenize, "FSTRING_END", None)

    fstring_start_line: int | None = None

    for tok_type, tok_string, tok_start, tok_end, _ in tokens:
        # Regular triple-quoted strings: single STRING token spanning lines
        if tok_type == tokenize.STRING and _NEWLINE_RE.search(tok_string):
            start_line = tok_start[0] - 1
            end_line = tok_end[0] - 1
            for i in range(start_line + 1, end_line + 1):
                if i < n:
                    protected[i] = True

        # Python 3.12+ f-strings: track FSTRING_START to FSTRING_END span
        elif FSTRING_START and tok_type == FSTRING_START:
            fstring_start_line = tok_start[0] - 1

        elif FSTRING_END and tok_type == FSTRING_END:
            if fstring_start_line is not None:
                end_line = tok_end[0] - 1
                for i in range(fstring_start_line + 1, end_line + 1):
                    if i < n:
                        protected[i] = True
                fstring_start_line = None

    return protected


def _strip_indent(line: str, shift: int) -> str:
    """Remove up to `shift` leading spaces/tabs.

    Never touches the line's content or terminator, so blank lines shorter
    than `shift` keep their newline instead of being swallowed.
    """
    i = 0
    while i < shift and i < len(line) and line[i] in " \t":
        i += 1
    return line[i:]


def _under_indented_string_lines(
    lines: list[str], protected: list[bool], base_shift: int
) -> list[bool]:
    """Mark protected lines belonging to an under-indented string block.

    A multiline string's interior is dedented with the surrounding code
    (the common case, equivalent to `textwrap.dedent`) unless the block is
    under-indented — i.e. some non-blank interior line has less leading
    whitespace than `base_shift`. Dedenting such a block would eat into its
    content, so the whole block is left untouched instead.
    """
    n = len(lines)
    keep = [False] * n
    i = 0
    while i < n:
        if not protected[i]:
            i += 1
            continue
        j = i
        block_min: float = float("inf")
        while j < n and protected[j]:
            line = lines[j]
            if line.strip():
                block_min = min(block_min, len(line) - len(line.lstrip()))
            j += 1
        if block_min != float("inf") and block_min < base_shift:
            for k in range(i, j):
                keep[k] = True
        i = j
    return keep


def smart_dedent(code: str) -> str:
    """Token-aware dedent.

    Strips base indentation (computed from code lines only) from every line.
    In the common case this is identical to `textwrap.dedent`. The exception
    is a multiline string whose interior is under-indented relative to the
    surrounding code: dedenting it would eat into the string's content, so its
    interior is left completely untouched.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except TokenError:
        return textwrap.dedent(code)

    lines = split_source_lines(code, keepends=True)
    protected = _get_protected_lines(code, tokens)

    min_indent: float = float("inf")
    for i, line in enumerate(lines):
        if protected[i] or not line.strip():
            continue
        min_indent = min(min_indent, len(line) - len(line.lstrip()))

    if min_indent in (0, float("inf")):
        return code

    base_shift = int(min_indent)
    keep = _under_indented_string_lines(lines, protected, base_shift)

    return "".join(
        line if keep[i] else _strip_indent(line, base_shift)
        for i, line in enumerate(lines)
    )


def fixed_dedent(text: str) -> str:
    """Dedent with robustness for AI-generated code with inconsistent indentation.

    Unlike textwrap.dedent, this pads lines that are under-indented to the
    base indentation level before dedenting, while preserving whitespace
    inside multiline string literals whose internal structure doesn't match
    the surrounding code's indentation.
    """
    lines = split_source_lines(text)

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except TokenError:
        tokens = []

    protected = _get_protected_lines(text, tokens)

    # Mirror str.splitlines(): a final line terminator yields a trailing ""
    # that we drop, so the result carries no spurious trailing newline. (The
    # trailing line is never inside a string, so `protected` stays aligned.)
    n = len(lines)
    if n > 1 and lines[-1] == "":
        n -= 1

    indent = None
    for i in range(n):
        if protected[i]:
            continue
        if content := lines[i].lstrip():
            indent = lines[i][: len(lines[i]) - len(content)]
            break

    if indent is None:
        # No code line to key off of (all-blank input): fall back to a plain
        # dedent, matching textwrap's normalization of whitespace-only lines.
        return textwrap.dedent(text)

    def refill(i: int, ln: str) -> str:
        if protected[i] or ln.startswith(indent):
            return ln
        return indent + ln

    return smart_dedent("\n".join(refill(i, lines[i]) for i in range(n)))
