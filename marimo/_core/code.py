# Copyright 2026 Marimo. All rights reserved.
"""Code identity for comparing document cells with their executions."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import sys
import token as token_types
import warnings
from tokenize import TokenError, tokenize

_SCHEME = f"py-ast-v1:{sys.version_info.major}.{sys.version_info.minor}"


def code_fingerprint(source: str) -> str:
    """Fingerprint the AST and final-expression suppression.

    Source positions are excluded. The prefix contains the algorithm and Python
    major/minor version. Invalid code uses its exact source.
    """
    payload: list[str | bool]
    code = source.replace("\u00a0", " ")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except (SyntaxError, ValueError):
        payload = ["source", source]
    else:
        suppress_output = (
            bool(tree.body)
            and isinstance(tree.body[-1], ast.Expr)
            and ends_with_semicolon(code)
        )
        payload = [
            "ast",
            ast.dump(tree, annotate_fields=True, include_attributes=False),
            suppress_output,
        ]
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return f"{_SCHEME}:{hashlib.sha256(encoded).hexdigest()}"


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
