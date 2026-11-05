# Copyright 2026 Marimo. All rights reserved.
"""Code identity for comparing document cells with their executions."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import token as token_types
import warnings
from tokenize import TokenError, tokenize
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Source positions, expression context, and the string prefix carry no
# meaning. `type_comment` is version dependent.
_SKIPPED_FIELDS = frozenset(
    {
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
        "ctx",
        "kind",
        "type_comment",
    }
)
# Nodes whose `value` is a literal, where None and False are meaningful.
_LITERAL_NODES = (ast.Constant, ast.MatchSingleton)


def code_fingerprint(source: str) -> str:
    """Fingerprint the AST and final-expression suppression.

    Source positions are excluded. Invalid code and AST processing limits
    fall back to the exact source.
    """
    code = source.replace("\u00a0", " ")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
        suppress_output = (
            bool(tree.body)
            and isinstance(tree.body[-1], ast.Expr)
            and ends_with_semicolon(code)
        )
        return ast_fingerprint(tree, suppress_output)
    except (SyntaxError, ValueError, RecursionError):
        return _digest(["source", source])


def ast_fingerprint(tree: ast.AST, suppress_output: bool = False) -> str:
    """Fingerprint an already parsed tree under the same scheme.

    The serialization is stable across Python versions: a field that a
    newer Python adds has a falsy value on older syntax and is skipped.
    """
    digest = hashlib.sha256()
    _feed(tree, digest.update)
    digest.update(b";" if suppress_output else b"")
    return digest.hexdigest()


def _feed(node: object, write: Callable[[bytes], object]) -> None:
    if isinstance(node, ast.AST):
        write(b"(" + type(node).__name__.encode("utf-8"))
        literal = isinstance(node, _LITERAL_NODES)
        for name in node._fields:
            if name in _SKIPPED_FIELDS:
                continue
            value = getattr(node, name, None)
            if not literal and not value and not isinstance(value, str):
                continue
            write(b" " + name.encode("utf-8") + b"=")
            _feed(value, write)
        write(b")")
    elif isinstance(node, list):
        write(b"[")
        for item in node:
            _feed(item, write)
        write(b"]")
    else:
        write(f"{type(node).__name__}:{node!r}".encode() + b"\0")


def _digest(payload: list[str | bool]) -> str:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ends_with_semicolon(code: str) -> bool:
    """Whether the last non-comment token is a semicolon."""
    try:
        tokens = list(
            tokenize(io.BytesIO(code.strip().encode("utf-8")).readline)
        )
    except (TokenError, SyntaxError):
        return code.rstrip().endswith(";")
    for token in reversed(tokens):
        if token.type in (
            token_types.ENDMARKER,
            token_types.NEWLINE,
            token_types.NL,
            token_types.COMMENT,
            token_types.INDENT,
            token_types.DEDENT,
            token_types.ENCODING,
        ):
            continue
        return token.string == ";"
    return False
