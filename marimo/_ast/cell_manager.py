# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import os
import random
import string
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Optional,
)

from marimo._ast.cell import Cell, CellConfig, CellId_t
from marimo._ast.compiler import cell_factory
from marimo._ast.models import CellData
from marimo._ast.names import DEFAULT_CELL_NAME
from marimo._ast.pytest import wrap_fn_for_pytest

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp


class CellManager:
    """A manager for cells in a marimo notebook.

    The CellManager is responsible for:
    1. Creating and managing unique cell IDs
    2. Registering and storing cell data (code, configuration, etc.)
    3. Providing access to cell information through various queries
    4. Managing both valid (parsable) and unparsable cells
    5. Handling cell decorators for the notebook interface

    Attributes:
        prefix (str): A prefix added to all cell IDs managed by this instance
        unparsable (bool): Flag indicating if any unparsable cells were encountered
        random_seed (random.Random): Seeded random number generator for deterministic cell ID creation
    """

    def __init__(self, prefix: str = "") -> None:
        """Initialize a new CellManager.

        Args:
            prefix (str, optional): Prefix to add to all cell IDs. Defaults to "".
        """
        self._cell_data: dict[CellId_t, CellData] = {}
        self.prefix = prefix
        self.unparsable = False
        self.random_seed = random.Random(42)
        self.seen_ids: set[CellId_t] = set()

    def create_cell_id(self) -> CellId_t:
        """Create a new unique cell ID.

        Returns:
            CellId_t: A new cell ID consisting of the manager's prefix followed by 4 random letters.
        """
        # 4 random letters
        _id = self.prefix + "".join(
            self.random_seed.choices(string.ascii_letters, k=4)
        )
        while _id in self.seen_ids:
            _id = self.prefix + "".join(
                self.random_seed.choices(string.ascii_letters, k=4)
            )
        self.seen_ids.add(_id)
        return _id

    # TODO: maybe remove this, it is leaky
    def cell_decorator(
        self,
        func: Callable[..., Any] | None,
        column: Optional[int],
        disabled: bool,
        hide_code: bool,
        app: InternalApp | None = None,
    ) -> Cell | Callable[..., Cell]:
        """Create a cell decorator for marimo notebook cells."""
        cell_config = CellConfig(
            column=column, disabled=disabled, hide_code=hide_code
        )

        def _register(func: Callable[..., Any]) -> Cell:
            # Use PYTEST_VERSION here, opposed to PYTEST_CURRENT_TEST, in
            # order to allow execution during test collection.
            is_top_level_pytest = (
                "PYTEST_VERSION" in os.environ
                and "PYTEST_CURRENT_TEST" not in os.environ
            )
            cell = cell_factory(
                func,
                cell_id=self.create_cell_id(),
                anonymous_file=app._app._anonymous_file if app else False,
                test_rewrite=is_top_level_pytest
                or (app is not None and app._app._pytest_rewrite),
            )
            cell._cell.configure(cell_config)
            self._register_cell(cell, app=app)
            # Manually set the signature for pytest.
            if is_top_level_pytest:
                func = wrap_fn_for_pytest(func, cell)
            # NB. in place metadata update.
            functools.wraps(func)(cell)
            return cell

        if func is None:
            # If the decorator was used with parentheses, func will be None,
            # and we return a decorator that takes the decorated function as an
            # argument
            def decorator(func: Callable[..., Any]) -> Cell:
                return _register(func)

            return decorator
        else:
            return _register(func)

    def _register_cell(
        self, cell: Cell, app: InternalApp | None = None
    ) -> None:
        if app is not None:
            cell._register_app(app)
        cell_impl = cell._cell
        self.register_cell(
            cell_id=cell_impl.cell_id,
            code=cell_impl.code,
            name=cell.name,
            config=cell_impl.config,
            cell=cell,
        )

    def register_cell(
        self,
        cell_id: Optional[CellId_t],
        code: str,
        config: Optional[CellConfig],
        name: str = DEFAULT_CELL_NAME,
        cell: Optional[Cell] = None,
    ) -> None:
        """Register a new cell with the manager.

        Args:
            cell_id: Unique identifier for the cell. If None, one will be generated
            code: The cell's source code
            config: Cell configuration (column, disabled state, etc.)
            name: Name of the cell, defaults to DEFAULT_CELL_NAME
            cell: Optional Cell object for valid cells
        """
        if cell_id is None:
            cell_id = self.create_cell_id()

        self._cell_data[cell_id] = CellData(
            cell_id=cell_id,
            code=code,
            name=name,
            config=config or CellConfig(),
            cell=cell,
        )

    def register_unparsable_cell(
        self,
        code: str,
        name: Optional[str],
        cell_config: CellConfig,
    ) -> None:
        """Register a cell that couldn't be parsed.

        Handles code formatting and registration of cells that couldn't be parsed
        into valid Python code.

        Args:
            code: The unparsable code string
            name: Optional name for the cell
            cell_config: Configuration for the cell
        """
        # - code.split("\n")[1:-1] disregards first and last lines, which are
        #   empty
        # - line[4:] removes leading indent in multiline string
        # - replace(...) unescapes double quotes
        # - rstrip() removes an extra newline
        code = "\n".join(
            [line[4:].replace('\\"', '"') for line in code.split("\n")[1:-1]]
        )

        self.register_cell(
            cell_id=self.create_cell_id(),
            code=code,
            config=cell_config,
            name=name or DEFAULT_CELL_NAME,
            cell=None,
        )

    def ensure_one_cell(self) -> None:
        """Ensure at least one cell exists in the manager.

        If no cells exist, creates an empty cell with default configuration.
        """
        if not self._cell_data:
            cell_id = self.create_cell_id()
            self.register_cell(
                cell_id=cell_id,
                code="",
                config=CellConfig(),
            )

    def cell_name(self, cell_id: CellId_t) -> str:
        """Get the name of a cell by its ID.

        Args:
            cell_id: The ID of the cell

        Returns:
            str: The name of the cell

        Raises:
            KeyError: If the cell_id doesn't exist
        """
        return self._cell_data[cell_id].name

    def names(self) -> Iterable[str]:
        """Get an iterator over all cell names.

        Returns:
            Iterable[str]: Iterator yielding each cell's name
        """
        for cell_data in self._cell_data.values():
            yield cell_data.name

    def codes(self) -> Iterable[str]:
        """Get an iterator over all cell codes.

        Returns:
            Iterable[str]: Iterator yielding each cell's source code
        """
        for cell_data in self._cell_data.values():
            yield cell_data.code

    def configs(self) -> Iterable[CellConfig]:
        """Get an iterator over all cell configurations.

        Returns:
            Iterable[CellConfig]: Iterator yielding each cell's configuration
        """
        for cell_data in self._cell_data.values():
            yield cell_data.config

    def valid_cells(
        self,
    ) -> Iterable[tuple[CellId_t, Cell]]:
        """Get an iterator over all valid (parsable) cells.

        Returns:
            Iterable[tuple[CellId_t, Cell]]: Iterator yielding tuples of (cell_id, cell)
            for each valid cell
        """
        for cell_data in self._cell_data.values():
            if cell_data.cell is not None:
                yield (cell_data.cell_id, cell_data.cell)

    def valid_cell_ids(self) -> Iterable[CellId_t]:
        """Get an iterator over IDs of all valid cells.

        Returns:
            Iterable[CellId_t]: Iterator yielding cell IDs of valid cells
        """
        for cell_data in self._cell_data.values():
            if cell_data.cell is not None:
                yield cell_data.cell_id

    def cell_ids(self) -> Iterable[CellId_t]:
        """Get an iterator over all cell IDs in registration order.

        Returns:
            Iterable[CellId_t]: Iterator yielding all cell IDs
        """
        return self._cell_data.keys()

    def has_cell(self, cell_id: CellId_t) -> bool:
        """Check if a cell with the given ID exists.

        Args:
            cell_id: The ID to check

        Returns:
            bool: True if the cell exists, False otherwise
        """
        return cell_id in self._cell_data

    def cells(
        self,
    ) -> Iterable[Optional[Cell]]:
        """Get an iterator over all Cell objects.

        Returns:
            Iterable[Optional[Cell]]: Iterator yielding Cell objects (or None for invalid cells)
        """
        for cell_data in self._cell_data.values():
            yield cell_data.cell

    def config_map(self) -> dict[CellId_t, CellConfig]:
        """Get a mapping of cell IDs to their configurations.

        Returns:
            dict[CellId_t, CellConfig]: Dictionary mapping cell IDs to their configurations
        """
        return {cid: cd.config for cid, cd in self._cell_data.items()}

    def cell_data(self) -> Iterable[CellData]:
        """Get an iterator over all cell data.

        Returns:
            Iterable[CellData]: Iterator yielding CellData objects for all cells
        """
        return self._cell_data.values()

    def cell_data_at(self, cell_id: CellId_t) -> CellData:
        """Get the cell data for a specific cell ID.

        Args:
            cell_id: The ID of the cell to get data for

        Returns:
            CellData: The cell's data

        Raises:
            KeyError: If the cell_id doesn't exist
        """
        return self._cell_data[cell_id]

    def get_cell_id_by_code(self, code: str) -> Optional[CellId_t]:
        """Find a cell ID by its code content.

        Args:
            code: The code to search for

        Returns:
            Optional[CellId_t]: The ID of the first cell with matching code,
            or None if no match is found
        """
        for cell_id, cell_data in self._cell_data.items():
            if cell_data.code == code:
                return cell_id
        return None

    def sort_cell_ids_by_similarity(
        self, prev_cell_manager: CellManager
    ) -> None:
        """Sort cell IDs by similarity to the current cell manager.

        This mutates the current cell manager.
        """
        prev_ids = list(prev_cell_manager.cell_ids())
        prev_codes = [data.code for data in prev_cell_manager.cell_data()]
        current_ids = list(self._cell_data.keys())
        current_codes = [data.code for data in self.cell_data()]
        sorted_ids = _match_cell_ids_by_similarity(
            prev_ids, prev_codes, current_ids, current_codes
        )
        assert len(sorted_ids) == len(list(self.cell_ids()))

        # Create mapping from new to old ids
        id_mapping = dict(zip(sorted_ids, current_ids))

        # Update the cell data in place
        self._cell_data = {
            new_id: self._cell_data[old_id]
            for new_id, old_id in id_mapping.items()
        }

        # Add the new ids to the set, so we don't reuse them in the future
        for _id in sorted_ids:
            self.seen_ids.add(_id)


def _match_cell_ids_by_similarity(
    prev_ids: list[CellId_t],
    prev_codes: list[str],
    next_ids: list[CellId_t],
    next_codes: list[str],
) -> list[CellId_t]:
    """Match cell IDs based on code similarity.

    Args:
        prev_ids: List of previous cell IDs, used as the set of possible IDs
        prev_codes: List of previous cell codes
        next_ids: List of next cell IDs, used only when more cells than prev_ids
        next_codes: List of next cell codes

    Returns:
        List of cell IDs matching next_codes, using prev_ids where possible
    """
    assert len(prev_codes) == len(prev_ids)
    assert len(next_codes) == len(next_ids)

    # Initialize result and tracking sets
    result: list[Optional[CellId_t]] = [None] * len(next_codes)
    used_positions: set[int] = set()
    used_prev_ids: set[CellId_t] = set()

    # Track which next_ids are new (not in prev_ids)
    new_next_ids = [p_id for p_id in next_ids if p_id not in prev_ids]
    new_id_idx = 0

    # First pass: exact matches using hash map
    next_code_to_idx: dict[str, list[int]] = {}
    for idx, code in enumerate(next_codes):
        next_code_to_idx.setdefault(code, []).append(idx)

    for prev_idx, prev_code in enumerate(prev_codes):
        if prev_ids[prev_idx] in used_prev_ids:
            continue
        if prev_code in next_code_to_idx:
            # Use first available matching position
            for next_idx in next_code_to_idx[prev_code]:
                if next_idx not in used_positions:
                    result[next_idx] = prev_ids[prev_idx]
                    used_positions.add(next_idx)
                    used_prev_ids.add(prev_ids[prev_idx])
                    break

    # If all positions filled, we're done
    if len(used_positions) == len(next_codes):
        return [_id for _id in result if _id is not None]  # type: ignore

    def similarity_score(s1: str, s2: str) -> int:
        """Fast similarity score based on common prefix and suffix.
        Returns lower score for more similar strings."""
        # Find common prefix length
        prefix_len = 0
        for c1, c2 in zip(s1, s2):
            if c1 != c2:
                break
            prefix_len += 1

        # Find common suffix length if strings differ in middle
        if prefix_len < min(len(s1), len(s2)):
            s1_rev = s1[::-1]
            s2_rev = s2[::-1]
            suffix_len = 0
            for c1, c2 in zip(s1_rev, s2_rev):
                if c1 != c2:
                    break
                suffix_len += 1
        else:
            suffix_len = 0

        # Return inverse similarity - shorter common affix means higher score
        return len(s1) + len(s2) - 2 * (prefix_len + suffix_len)

    # Filter out used positions and ids for similarity matrix
    remaining_prev_indices = [
        i for i, pid in enumerate(prev_ids) if pid not in used_prev_ids
    ]
    remaining_next_indices = [
        i for i in range(len(next_codes)) if i not in used_positions
    ]

    # Create similarity matrix only for remaining cells
    similarity_matrix: list[list[int]] = []
    for prev_idx in remaining_prev_indices:
        row: list[int] = []
        for next_idx in remaining_next_indices:
            score = similarity_score(
                prev_codes[prev_idx], next_codes[next_idx]
            )
            row.append(score)
        similarity_matrix.append(row)

    # Second pass: best matches for remaining positions
    for matrix_prev_idx, prev_idx in enumerate(remaining_prev_indices):
        # Find best match among unused positions
        min_score = float("inf")  # type: ignore
        best_next_matrix_idx = None
        for matrix_next_idx, score in enumerate(
            similarity_matrix[matrix_prev_idx]
        ):
            if score < min_score:
                min_score = score
                best_next_matrix_idx = matrix_next_idx

        if best_next_matrix_idx is not None:
            next_idx = remaining_next_indices[best_next_matrix_idx]
            result[next_idx] = prev_ids[prev_idx]
            used_positions.add(next_idx)
            used_prev_ids.add(prev_ids[prev_idx])

    # Fill remaining positions with new next_ids
    for i in range(len(next_codes)):
        if result[i] is None:
            if new_id_idx < len(new_next_ids):
                result[i] = new_next_ids[new_id_idx]
                new_id_idx += 1

    return [_id for _id in result if _id is not None]  # type: ignore
