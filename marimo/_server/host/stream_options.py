# Copyright 2026 Marimo. All rights reserved.
"""Subscription options shared by host and session stream routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, get_args

from marimo._core import protocol

if TYPE_CHECKING:
    from starlette.requests import HTTPConnection

OBJECT_KINDS = frozenset(get_args(get_args(protocol.ObjectKind)[0])) | {
    "marimo"
}


def cursor(connection: HTTPConnection) -> str | None:
    raw = connection.headers.get("Last-Event-ID")
    query = connection.query_params.get("cursor")
    if query is not None:
        if raw is not None and raw != query:
            raise ValueError("Conflicting cursors")
        raw = query
    if raw == "":
        raise ValueError("Last-Event-ID is empty")
    return raw


def kinds(connection: HTTPConnection) -> set[str] | None:
    asked = connection.query_params.get("kinds")
    if not asked:
        return None
    wanted = {kind for kind in asked.split(",") if kind}
    unknown = wanted - OBJECT_KINDS
    if unknown:
        raise ValueError(
            f"kinds has no kind named {', '.join(sorted(unknown))}"
        )
    return wanted
