"""Token-aware dedent that preserves multiline string literal whitespace."""
from __future__ import annotations

import io
import textwrap
import tokenize
from tokenize import TokenError


def smart_dedent(code: str) -> str:
    lines = code.splitlines(keepends=True)
    n = len(lines)
    protected = [False] * n

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except TokenError:
        return textwrap.dedent(code)

    for tok_type, tok_string, tok_start, tok_end, _ in tokens:
        if tok_type == tokenize.STRING and "\n" in tok_string:
            start_line = tok_start[0] - 1
            end_line = tok_end[0] - 1
            for i in range(start_line + 1, end_line + 1):
                if i < n:
                    protected[i] = True

    min_indent: float = float("inf")
    for i, line in enumerate(lines):
        if protected[i]:
            continue
        stripped = line.lstrip()
        if not stripped:
            continue
        min_indent = min(min_indent, len(line) - len(stripped))

    if min_indent in (0, float("inf")):
        return code

    result = []
    for i, line in enumerate(lines):
        if protected[i]:
            result.append(line)
        else:
            result.append(
                line[int(min_indent):]
                if line[:int(min_indent)].strip() == ""
                else line
            )

    return "".join(result)


def _get_protected_lines(code: str) -> list[bool]:
    """Return a bool list marking lines inside multiline string literals."""
    lines = code.splitlines(keepends=True)
    n = len(lines)
    protected = [False] * n
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except TokenError:
        return protected
    for tok_type, tok_string, tok_start, tok_end, _ in tokens:
        if tok_type == tokenize.STRING and "\n" in tok_string:
            start_line = tok_start[0] - 1
            end_line = tok_end[0] - 1
            for i in range(start_line + 1, end_line + 1):
                if i < n:
                    protected[i] = True
    return protected
