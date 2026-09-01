# Copyright 2026 Marimo. All rights reserved.

from marimo import _loggers
from marimo._data._external_storage.models import (
    StorageEntry,
    StorageListResult,
)

LOGGER = _loggers.marimo_logger()


def parse_page_offset(page_token: str | None) -> int:
    if page_token is None:
        return 0
    try:
        offset = int(page_token)
    except ValueError as exc:
        raise ValueError(f"Invalid storage page token: {page_token}") from exc
    if offset < 0:
        raise ValueError(f"Invalid storage page token: {page_token}")
    return offset


def paginate_entries(
    entries: list[StorageEntry],
    *,
    offset: int,
    limit: int,
) -> StorageListResult:
    if limit < 1:
        raise ValueError("Storage list limit must be positive")

    total_entries = len(entries)
    if total_entries > limit:
        LOGGER.debug(
            "Fetched %s entries, returning page offset %s with limit %s",
            total_entries,
            offset,
            limit,
        )

    end = offset + limit
    has_next_page = end < total_entries
    next_page_token = str(end) if has_next_page else None
    return StorageListResult(
        entries=entries[offset:end],
        next_page_token=next_page_token,
    )
