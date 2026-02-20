# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import random
import string
from uuid import UUID, uuid4

from marimo._types.ids import CellId_t


class CellIdGenerator:
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix
        self.random_seed = random.Random(42)
        self.seen_ids: set[CellId_t] = set()

    def create_cell_id(self) -> CellId_t:
        """Create a new unique cell ID.

        Returns:
            CellId_t: A new cell ID consisting of the manager's prefix followed by 4 random letters.
        """
        attempts = 0
        while attempts < 100:
            # 4 random letters
            _id = self.prefix + "".join(
                self.random_seed.choices(string.ascii_letters, k=4)
            )
            if _id not in self.seen_ids:
                self.seen_ids.add(CellId_t(_id))
                return CellId_t(_id)
            attempts += 1

        raise ValueError(
            f"Failed to create a unique cell ID after {attempts} attempts"
        )


def external_prefix() -> str:
    """Get the prefix for external cell IDs."""
    return str(uuid4())


def is_external_cell_id(cell_id: CellId_t) -> bool:
    """
    Check if cell_id is from an embedded/nested app.

    Detects only the embedded case: a UUID4 prefix (36 chars) followed by
    a cell ID suffix (4+ chars). Returns False for all other formats,
    including normal 4-char cell IDs and bare UUIDs (e.g. from VSCode).

    Cell ID formats:
        - "Hbol"              -> normal cell (4 chars)
        - "<uuid>"            -> VSCode cell (36 chars)
        - "<uuid>Hbol"        -> embedded cell (40+ chars) ← detected here

    >>> is_external_cell_id("c9bf9e57-1685-4c89-bafb-ff5af830be8aHbol")
    True
    >>> is_external_cell_id("Hbol")
    False
    >>> is_external_cell_id("c9bf9e57-1685-4c89-bafb-ff5af830be8a")
    False
    """

    cell_id_str = str(cell_id)
    # External IDs are UUID (36 chars) + suffix; bare UUIDs are not external
    if len(cell_id_str) <= 36:
        return False
    uuid_to_test = cell_id_str[:36]
    try:
        uuid_obj = UUID(uuid_to_test, version=4)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test
