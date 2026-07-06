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


def _get_protected_lines(code: str, tokens: list) -> list[bool]:
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


def _compute_block_shifts(
    lines: list[str], protected: list[bool], base_shift: int
) -> list[int]:
    """Compute the per-line dedent shift for protected (string-literal) lines.

    A contiguous run of protected lines is only shifted by the same amount
    as the surrounding code (`base_shift`) if the block's own minimum
    internal indentation is at least `base_shift` — i.e. the block is
    "in step" with the surrounding code's indentation (e.g. a markdown
    block written to visually align with the code around it) and can
    safely absorb the same dedent without disturbing its relative
    structure. If the block is less indented than that in places (e.g.
    hand-crafted data with deliberately varied indentation), it is left
    completely untouched.
    """
    n = len(lines)
    block_shift = [0] * n
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
                stripped = line.lstrip()
                block_min = min(block_min, len(line) - len(stripped))
            j += 1
        if block_min == float("inf") or block_min >= base_shift:
            for k in range(i, j):
                block_shift[k] = base_shift
        i = j
    return block_shift


def smart_dedent(code: str) -> str:
    """Token-aware dedent.

    Strips base indentation from code lines. Lines inside multiline string
    literals (triple-quoted strings of any prefix: regular, f-strings,
    r-strings, b-strings, etc) only participate in the same dedent if doing
    so wouldn't disturb the string block's own internal indentation
    structure — otherwise they are left completely untouched.
    """
    lines = split_source_lines(code, keepends=True)

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except TokenError:
        return textwrap.dedent(code)

    protected = _get_protected_lines(code, tokens)

    min_indent: float = float("inf")
    for i, line in enumerate(lines):
        if protected[i]:
            continue
        if not line.strip():
            continue
        stripped = line.lstrip()
        min_indent = min(min_indent, len(line) - len(stripped))

    if min_indent in (0, float("inf")):
        return code

    base_shift = int(min_indent)
    block_shift = _compute_block_shifts(lines, protected, base_shift)

    result = []
    for i, line in enumerate(lines):
        shift = block_shift[i] if protected[i] else base_shift
        if shift <= 0:
            result.append(line)
        else:
            result.append(
                line[shift:] if line[:shift].strip() == "" else line
            )

    return "".join(result)


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

    indent = None
    for i, line in enumerate(lines):
        if protected[i]:
            continue
        if content := line.lstrip():
            indent = line[: len(line) - len(content)]
            break

    if indent is None:
        return smart_dedent(text)

    def refill(i: int, ln: str) -> str:
        if protected[i]:
            return ln
        if not ln.startswith(indent):
            return indent + ln
        return ln

    return smart_dedent("\n".join(refill(i, ln) for i, ln in enumerate(lines)))
