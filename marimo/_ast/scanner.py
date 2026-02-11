# Copyright 2026 Marimo. All rights reserved.
"""Tokenizer-based cell boundary scanner for marimo notebooks.

Uses Python's tokenize module to find cell boundaries, correctly
ignoring `@app.cell` inside strings/comments. Falls back to
line-based scanning when the tokenizer fails (e.g. unterminated strings).
"""

from __future__ import annotations

import ast
import enum
import io
import re
import token as token_types
import tokenize as tokenize_mod
from dataclasses import dataclass
from typing import Optional

# Cell boundary types
CELL_TYPES = frozenset({"cell", "function", "class_definition"})


@dataclass
class ScannedCell:
    kind: str  # "cell", "function", "class_definition", "setup", "unparsable"
    name: str | None  # function/class name from def/class line
    source: str  # full raw source (decorator + def + body)
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed


@dataclass
class ScanResult:
    preamble: str  # everything before first cell boundary
    cells: list[ScannedCell]  # scanned cells in file order
    run_guard_line: int | None  # line number of `if __name__` guard


class _State(enum.Enum):
    IDLE = enum.auto()
    # @app.cell / @app.function / @app.class_definition
    AT = enum.auto()
    AT_APP = enum.auto()
    AT_APP_DOT = enum.auto()
    AT_APP_DOT_KIND = enum.auto()
    AT_DECORATOR_ARGS = enum.auto()
    # with app.setup(...):
    WITH = enum.auto()
    WITH_APP = enum.auto()
    WITH_APP_DOT = enum.auto()
    WITH_SETUP = enum.auto()
    # app._unparsable_cell(
    APP_DIRECT = enum.auto()
    APP_DIRECT_DOT = enum.auto()
    APP_DIRECT_UNPARSABLE = enum.auto()
    # if __name__ == "__main__":
    IF = enum.auto()
    IF_NAME = enum.auto()


class _BoundaryDetector:
    """State machine over the token stream to detect cell boundaries.

    Boundaries are identified by token sequences at column 0:
    - Decorator: @app.cell|function|class_definition [(...)]
    - Setup: with app.setup(...):
    - Unparsable: app._unparsable_cell(
    - Run guard: if __name__ ==
    """

    def __init__(self) -> None:
        self.boundaries: list[tuple[int, str, int]] = []
        # (start_line, kind, end_of_decorator_line)
        self.run_guard_line: int | None = None
        self._reset()

    def _reset(self) -> None:
        self._state = _State.IDLE
        self._start_line = 0
        self._kind = ""
        self._paren_depth = 0

    def feed(self, tok: tokenize_mod.TokenInfo) -> None:
        ttype = tok.type
        tstr = tok.string
        row, col = tok.start

        if self._state is _State.IDLE:
            if col != 0:
                return
            if ttype == token_types.OP and tstr == "@":
                self._state = _State.AT
                self._start_line = row
            elif ttype == token_types.NAME and tstr == "with":
                self._state = _State.WITH
                self._start_line = row
            elif ttype == token_types.NAME and tstr == "app":
                self._state = _State.APP_DIRECT
                self._start_line = row
            elif ttype == token_types.NAME and tstr == "if":
                self._state = _State.IF
                self._start_line = row
            return

        # @app.cell(...) decorator
        if self._state is _State.AT:
            if ttype == token_types.NAME and tstr == "app":
                self._state = _State.AT_APP
            else:
                self._reset()
        elif self._state is _State.AT_APP:
            if ttype == token_types.OP and tstr == ".":
                self._state = _State.AT_APP_DOT
            else:
                self._reset()
        elif self._state is _State.AT_APP_DOT:
            if ttype == token_types.NAME and tstr in CELL_TYPES:
                self._kind = tstr
                self._state = _State.AT_APP_DOT_KIND
            else:
                self._reset()
        elif self._state is _State.AT_APP_DOT_KIND:
            if ttype == token_types.OP and tstr == "(":
                self._paren_depth = 1
                self._state = _State.AT_DECORATOR_ARGS
            elif ttype in (
                token_types.NEWLINE,
                token_types.NL,
                token_types.COMMENT,
            ):
                self.boundaries.append((self._start_line, self._kind, row))
                self._reset()
            else:
                self._reset()
        elif self._state is _State.AT_DECORATOR_ARGS:
            if ttype == token_types.OP and tstr == "(":
                self._paren_depth += 1
            elif ttype == token_types.OP and tstr == ")":
                self._paren_depth -= 1
                if self._paren_depth == 0:
                    self.boundaries.append((self._start_line, self._kind, row))
                    self._reset()

        # with app.setup(...):
        elif self._state is _State.WITH:
            if ttype == token_types.NAME and tstr == "app":
                self._state = _State.WITH_APP
            else:
                self._reset()
        elif self._state is _State.WITH_APP:
            if ttype == token_types.OP and tstr == ".":
                self._state = _State.WITH_APP_DOT
            else:
                self._reset()
        elif self._state is _State.WITH_APP_DOT:
            if ttype == token_types.NAME and tstr == "setup":
                self._kind = "setup"
                self._state = _State.WITH_SETUP
            else:
                self._reset()
        elif self._state is _State.WITH_SETUP:
            if ttype == token_types.OP and tstr == ":":
                self.boundaries.append((self._start_line, "setup", row))
                self._reset()
            elif ttype in (token_types.NEWLINE, token_types.NL):
                self._reset()

        # app._unparsable_cell(
        elif self._state is _State.APP_DIRECT:
            if ttype == token_types.OP and tstr == ".":
                self._state = _State.APP_DIRECT_DOT
            else:
                self._reset()
        elif self._state is _State.APP_DIRECT_DOT:
            if ttype == token_types.NAME and tstr == "_unparsable_cell":
                self._kind = "unparsable"
                self._state = _State.APP_DIRECT_UNPARSABLE
            else:
                self._reset()
        elif self._state is _State.APP_DIRECT_UNPARSABLE:
            if ttype == token_types.OP and tstr == "(":
                self.boundaries.append((self._start_line, "unparsable", row))
                self._reset()
            else:
                self._reset()

        # if __name__ == "__main__":
        elif self._state is _State.IF:
            if ttype == token_types.NAME and tstr == "__name__":
                self._state = _State.IF_NAME
            else:
                self._reset()
        elif self._state is _State.IF_NAME:
            if ttype == token_types.OP and tstr == "==":
                self.run_guard_line = self._start_line
                self._reset()
            else:
                self._reset()


def _try_tokenize(
    source: str,
) -> tuple[list[tokenize_mod.TokenInfo], Optional[tuple[int, Exception]]]:
    """Tokenize source, returning tokens produced + optional error info."""
    tokens: list[tokenize_mod.TokenInfo] = []
    readline = io.StringIO(source).readline
    try:
        for tok in tokenize_mod.generate_tokens(readline):
            tokens.append(tok)  # noqa: PERF402
    except tokenize_mod.TokenError as e:
        return tokens, (
            e.args[1][0] if len(e.args) > 1 else len(source.splitlines()),
            e,
        )
    except IndentationError as e:
        line = e.lineno or len(source.splitlines())
        return tokens, (line, e)
    return tokens, None


# Patterns for line-based recovery scanning
_BOUNDARY_LINE_RE = re.compile(
    r"^(?:@app\.|with\s+app\.|app\._unparsable_cell|if\s+__name__\s*==)"
)


def scan_notebook(source: str) -> ScanResult:
    """Scan a notebook source string for cell boundaries.

    Uses the tokenizer for accurate detection (handles @app.cell
    inside strings/comments correctly). Falls back to line-based
    recovery when the tokenizer fails.
    """
    if not source.strip():
        return ScanResult(preamble="", cells=[], run_guard_line=None)

    lines = source.splitlines(keepends=True)
    total_lines = len(lines)

    # Collect all boundaries by processing chunks
    all_boundaries: list[tuple[int, str, int]] = []
    run_guard_line: int | None = None

    offset = 0  # 0-indexed line offset for current chunk
    while offset < total_lines:
        chunk = "".join(lines[offset:])
        tokens, error_info = _try_tokenize(chunk)

        # Process tokens through boundary detector
        detector = _BoundaryDetector()
        for tok in tokens:
            detector.feed(tok)

        # Adjust line numbers by offset (tokens are 1-indexed within chunk)
        for start, kind, end in detector.boundaries:
            all_boundaries.append((start + offset, kind, end + offset))
        if detector.run_guard_line is not None and run_guard_line is None:
            run_guard_line = detector.run_guard_line + offset

        if error_info is None:
            break  # Successfully tokenized everything

        # Error recovery: scan forward from error line for boundaries
        error_line_in_chunk, _exc = error_info
        error_line_abs = error_line_in_chunk + offset
        found_restart = False

        for candidate_line_0 in range(error_line_abs, total_lines):
            line_text = lines[candidate_line_0]
            if _BOUNDARY_LINE_RE.match(line_text):
                # Try to tokenize from this candidate
                candidate_chunk = "".join(lines[candidate_line_0:])
                test_tokens, _test_err = _try_tokenize(candidate_chunk)
                # Check if we can find at least one boundary
                test_det = _BoundaryDetector()
                for tok in test_tokens:
                    test_det.feed(tok)
                    # One boundary is enough to validate
                    if (
                        test_det.boundaries
                        or test_det.run_guard_line is not None
                    ):
                        break

                if test_det.boundaries or test_det.run_guard_line is not None:
                    offset = candidate_line_0
                    found_restart = True
                    break

        if not found_restart:
            break  # No more boundaries to find

    # Sort boundaries by line number
    all_boundaries.sort(key=lambda b: b[0])

    # For decorator-style boundaries (@app.cell etc.), look backwards
    # for preceding decorator lines (e.g. @wrapper) that belong to
    # the same decorated function/class.
    adjusted_boundaries: list[tuple[int, str, int]] = []
    for start_line, kind, dec_end in all_boundaries:
        if kind in CELL_TYPES:
            # Scan backwards from the @app.* line for decorator lines
            adjusted_start = start_line
            line_idx = start_line - 2  # 0-indexed, one line before
            while line_idx >= 0:
                line = lines[line_idx].strip()
                if line.startswith("@"):
                    adjusted_start = line_idx + 1  # 1-indexed
                    line_idx -= 1
                elif not line:
                    # Skip blank lines between decorators
                    line_idx -= 1
                else:
                    break
            adjusted_boundaries.append((adjusted_start, kind, dec_end))
        else:
            adjusted_boundaries.append((start_line, kind, dec_end))
    all_boundaries = adjusted_boundaries

    # Build cells from boundaries
    cells: list[ScannedCell] = []

    # Preamble: everything before the first boundary
    if all_boundaries:
        first_boundary_line = all_boundaries[0][0]  # 1-indexed
        preamble = "".join(lines[: first_boundary_line - 1])
    else:
        preamble = source

    for i, (start_line, kind, _dec_end) in enumerate(all_boundaries):
        # Determine end of this cell: start of next boundary or run guard or EOF
        if i + 1 < len(all_boundaries):
            next_start = all_boundaries[i + 1][0]
        elif run_guard_line is not None:
            next_start = run_guard_line
        else:
            next_start = total_lines + 1

        # Extract source (1-indexed → 0-indexed)
        cell_source = "".join(lines[start_line - 1 : next_start - 1]).rstrip(
            "\n"
        )
        if not cell_source:
            cell_source = ""

        end_line = next_start - 1
        # Strip trailing blank lines from end_line
        while end_line > start_line and not lines[end_line - 1].strip():
            end_line -= 1

        # Extract name from the def/class line after decorator
        name = _extract_name_from_cell(
            kind, lines, start_line - 1, next_start - 1
        )

        cells.append(
            ScannedCell(
                kind=kind,
                name=name,
                source=cell_source,
                start_line=start_line,
                end_line=end_line,
            )
        )

    return ScanResult(
        preamble=preamble, cells=cells, run_guard_line=run_guard_line
    )


def _extract_name_from_cell(
    kind: str,
    lines: list[str],
    start_0: int,
    end_0: int,
) -> str | None:
    """Extract the function/class name from lines following a decorator."""
    if kind in ("setup",):
        return None
    if kind == "unparsable":
        # For unparsable cells, try to find `name="..."` in the call
        for line in lines[start_0:end_0]:
            match = re.search(r'name\s*=\s*["\'](\w+)["\']', line)
            if match:
                return match.group(1)
        return None

    # Look for def/class after the decorator line
    for line_idx in range(start_0 + 1, min(end_0, len(lines))):
        line = lines[line_idx]
        match = re.match(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)", line)
        if match:
            return match.group(1)
    return None


def _extract_body_code(cell_source: str, kind: str) -> str:
    """Extract just the body code from a cell source string.

    Strips decorator lines, def/class/with header, and trailing return.
    Used when a cell fails ast.parse() to get the body for UnparsableCell.
    """
    from marimo._ast.parse import fixed_dedent

    if kind == "unparsable":
        # Already app._unparsable_cell(...) — return as-is
        return cell_source

    lines = cell_source.splitlines(keepends=True)
    body_start = _find_body_start(lines, kind)

    if body_start >= len(lines):
        return ""

    body_lines = list(lines[body_start:])

    # Strip trailing return at body indentation level
    _strip_trailing_return(body_lines)

    body = "".join(body_lines)
    return fixed_dedent(body).strip()


def _find_body_start(lines: list[str], kind: str) -> int:
    """Find the line index where the body starts (after header).

    For cell/function/class_definition: skip @decorators, then def/class
    header (handling multi-line signatures).
    For setup: skip `with app.setup():` header.
    """
    i = 0

    if kind in CELL_TYPES:
        # Skip decorator lines
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("@") or not stripped:
                i += 1
            else:
                break

    # Now find the end of the def/class/with header (the colon at depth 0)
    paren_depth = 0
    while i < len(lines):
        line = lines[i]
        j = 0
        while j < len(line):
            ch = line[j]
            if ch in ('"', "'"):
                # Skip string literals
                quote = ch
                j += 1
                if j + 1 < len(line) and line[j : j + 2] == quote * 2:
                    # Triple quote — skip to closing
                    j += 2
                    end = line.find(quote * 3, j)
                    if end >= 0:
                        j = end + 3
                    else:
                        j = len(line)
                    continue
                # Single quote string
                while j < len(line) and line[j] != quote:
                    if line[j] == "\\":
                        j += 1  # skip escaped char
                    j += 1
                j += 1  # skip closing quote
                continue
            if ch == "#":
                break  # rest is comment
            if ch in ("(", "[", "{"):
                paren_depth += 1
            elif ch in (")", "]", "}"):
                paren_depth -= 1
            elif ch == ":" and paren_depth == 0:
                # Found the header-ending colon
                return i + 1
            j += 1
        i += 1

    # Couldn't find colon — return all lines as body
    return 0


def _strip_trailing_return(body_lines: list[str]) -> None:
    """Remove trailing return statement from body lines (in-place).

    Only strips a return at the body's indentation level (top-level
    within the function), not nested returns.
    """
    # Find body indentation from first non-blank line
    body_indent = ""
    for line in body_lines:
        stripped = line.strip()
        if stripped:
            body_indent = line[: len(line) - len(line.lstrip())]
            break

    # From the bottom, skip blank lines, then check for return
    idx = len(body_lines) - 1
    while idx >= 0 and not body_lines[idx].strip():
        idx -= 1

    if idx >= 0:
        line = body_lines[idx]
        line_indent = line[: len(line) - len(line.lstrip())]
        line_stripped = line.strip()
        if line_indent == body_indent and (
            line_stripped == "return"
            or line_stripped.startswith("return ")
            or line_stripped.startswith("return\t")
            or line_stripped.startswith("return(")
        ):
            # Remove the return line and any trailing blank lines after it
            del body_lines[idx:]


def _build_unparsable_node(
    code: str,
    name: str | None,
    start_line: int,
) -> ast.Expr:
    """Build a synthetic app._unparsable_cell(...) AST node.

    Must pass is_unparsable_cell() check in parse.py.
    """
    # Build: app._unparsable_cell("code", name="name")
    keywords = []
    if name is not None:
        keywords.append(
            ast.keyword(
                arg="name",
                value=ast.Constant(value=name),
            )
        )

    node = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="app", ctx=ast.Load()),
                attr="_unparsable_cell",
                ctx=ast.Load(),
            ),
            args=[ast.Constant(value=code)],
            keywords=keywords,
        )
    )
    # Set line numbers
    ast.fix_missing_locations(node)
    ast.increment_lineno(node, start_line - 1)
    # Mark as scanner-generated so parse_body can add a violation
    node._scanner_generated = True  # type: ignore[attr-defined]
    return node


def _build_run_guard_node(start_line: int) -> ast.If:
    """Build a synthetic if __name__ == "__main__": app.run() node."""
    tree = ast.parse('if __name__ == "__main__": app.run()')
    node = tree.body[0]
    ast.increment_lineno(node, start_line - 1)
    return node


def _has_cell_boundaries(source: str) -> bool:
    """Quick check whether source has any cell boundary markers."""
    return (
        "@app.cell" in source
        or "@app.function" in source
        or "@app.class_definition" in source
        or "with app.setup" in source
        or "app._unparsable_cell" in source
    )


def scan_parse_fallback(source: str, filepath: str) -> list[ast.stmt]:
    """Fallback parser: scan for cell boundaries, parse each cell individually.

    Called when ast.parse() on the full file fails due to syntax errors.
    Returns AST nodes with unparsable cells wrapped as app._unparsable_cell().
    """
    from marimo._ast.parse import ast_parse

    if not _has_cell_boundaries(source):
        # Not a notebook — re-raise the original error
        ast.parse(source, filename=filepath)
        return []  # unreachable

    scan = scan_notebook(source)
    nodes: list[ast.stmt] = []

    # Preamble
    if scan.preamble.strip():
        try:
            tree = ast_parse(scan.preamble, filename=filepath)
            nodes.extend(tree.body)
        except SyntaxError:
            raise  # Preamble errors are fatal

    # Cells
    for cell in scan.cells:
        try:
            cell_tree = ast_parse(cell.source, filename=filepath)
            ast.increment_lineno(cell_tree, cell.start_line - 1)
            nodes.extend(cell_tree.body)
        except SyntaxError:
            inner_code = _extract_body_code(cell.source, cell.kind)
            nodes.append(
                _build_unparsable_node(inner_code, cell.name, cell.start_line)
            )

    # Run guard
    if scan.run_guard_line is not None:
        nodes.append(_build_run_guard_node(scan.run_guard_line))

    return nodes
