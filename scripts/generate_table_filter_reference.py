# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from pathlib import Path

import msgspec

from marimo._server.ai.table_filter import (
    DEFAULT_TABLE_FILTER_ASSETS,
    build_table_filter_reference,
)


def main() -> None:
    """Regenerate the reference fixture for frontend parser and adapter tests."""
    operations = DEFAULT_TABLE_FILTER_ASSETS.operations
    fixture = {
        "version": 1,
        "text": build_table_filter_reference(operations),
        "operations": msgspec.json.decode(msgspec.json.encode(operations)),
    }
    destination = (
        Path(__file__).resolve().parents[1]
        / "frontend/src/components/data-table/__tests__/fixtures/table-filter-reference.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(fixture, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
