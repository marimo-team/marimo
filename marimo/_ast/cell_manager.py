# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    TypeVar,
)

if sys.version_info < (3, 10):
    from typing_extensions import ParamSpec, TypeAlias
else:
    from typing import ParamSpec, TypeAlias

from marimo import _loggers
from marimo._ast.cell import Cell, CellConfig
from marimo._ast.cell_id import CellIdGenerator
from marimo._ast.compiler import (
    cell_factory,
    context_cell_factory,
    ir_cell_factory,
    toplevel_cell_factory,
)
from marimo._ast.models import CellData
from marimo._ast.names import DEFAULT_CELL_NAME, SETUP_CELL_NAME
from marimo._ast.pytest import process_for_pytest
from marimo._schemas.serialization import (
    CellDef,
    SetupCell,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import FrameType

    from marimo._ast.app import InternalApp

P = ParamSpec("P")
R = TypeVar("R")
Fn: TypeAlias = Callable[P, R]
Cls: TypeAlias = type
Obj: TypeAlias = "Cls | Fn[P, R]"

LOGGER = _loggers.marimo_logger()


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
    """

    def __init__(self, prefix: str = "") -> None:
        """Initialize a new CellManager.

        Args:
            prefix (str, optional): Prefix to add to all cell IDs. Defaults to "".
        """
        self._cell_data: dict[CellId_t, CellData] = {}
        self.prefix = prefix
        self.unparsable = False
        self._cell_id_generator = CellIdGenerator(prefix)

    def create_cell_id(self) -> CellId_t:
        """Create a new unique cell ID.

        Returns:
            CellId_t: A new cell ID consisting of the manager's prefix followed by 4 random letters.
        """
        return self._cell_id_generator.create_cell_id()

    def cell_decorator(
        self,
        obj: Obj[P, R] | None,
        column: Optional[int],
        disabled: bool,
        hide_code: bool,
        app: InternalApp | None = None,
        *,
        top_level: bool = False,
    ) -> Cell | Obj[P, R] | Callable[[Obj[P, R]], Cell | Obj[P, R]]:
        """Create a cell decorator for marimo notebook cells."""
        # NB. marimo also statically loads notebooks via the marimo/_ast/load
        # path. This code is only called when run as a script or imported as a
        # module.
        cell_config = CellConfig(
            column=column, disabled=disabled, hide_code=hide_code
        )

        def _register(obj: Obj[P, R]) -> Cell | Obj[P, R]:
            # Use PYTEST_VERSION here, opposed to PYTEST_CURRENT_TEST, in
            # order to allow execution during test collection.
            is_top_level_pytest = (
                "PYTEST_VERSION" in os.environ
                and "PYTEST_CURRENT_TEST" not in os.environ
            ) or "MARIMO_PYTEST_WASM" in os.environ
            factory: Callable[..., Cell] = (
                toplevel_cell_factory if top_level else cell_factory
            )
            try:
                cell = factory(
                    obj,
                    cell_id=self.create_cell_id(),
                    anonymous_file=app._app._anonymous_file if app else False,
                    test_rewrite=is_top_level_pytest
                    or (app is not None and app._app._pytest_rewrite),
                )
            except TypeError as e:
                LOGGER.debug(
                    f"Failed to register cell: {e}. Expected class or function,"
                    f"got {type(obj)}."
                )
                # Top level definitions can wrap non-functions or classes.
                # Since static parsing makes it possible to load and create a
                # notebook like this, importing the notebooks shouldn't fail
                # either.
                if top_level:
                    return obj
                # If it is not a top-level definition, something is very wrong
                raise ValueError(
                    "Unexpected failure. Please report this error to "
                    "github.com/marimo-team/marimo/issues."
                ) from e

            cell._cell.configure(cell_config)
            self._register_cell(cell, app=app)

            # Top level functions are exposed as the function itself.
            if top_level:
                return obj

            # Manually set the signature for pytest.
            if is_top_level_pytest:
                # NB. in place metadata update.
                process_for_pytest(obj, cell)
            return cell

        if obj is None:
            # If the decorator was used with parentheses, func will be None,
            # and we return a decorator that takes the decorated function as an
            # argument
            def decorator(obj: Obj[P, R]) -> Cell | Obj[P, R]:
                return _register(obj)

            return decorator
        else:
            return _register(obj)

    def cell_context(
        self,
        frame: FrameType,
        app: InternalApp | None = None,
        config: Optional[CellConfig] = None,
    ) -> Cell:
        """Registers cells when called through a context block."""
        cell = context_cell_factory(
            cell_id=CellId_t(SETUP_CELL_NAME),
            # NB. carry along the frame from the initial call.
            frame=frame,
        )
        cell._cell.configure(config or CellConfig())
        self._register_cell(cell, app=app)
        return cell

    def _register_cell(
        self, cell: Cell, app: InternalApp | None = None
    ) -> None:
        if app is None:
            raise ValueError("app must not be None")
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

    def register_ir_cell(
        self, cell_def: CellDef, app: InternalApp | None = None
    ) -> None:
        if isinstance(cell_def, SetupCell):
            cell_id = CellId_t(SETUP_CELL_NAME)
        else:
            cell_id = self.create_cell_id()
        cell = ir_cell_factory(cell_def, cell_id=cell_id)
        cell_config = CellConfig.from_dict(
            cell_def.options,
        )
        cell._cell.configure(cell_config)
        self._register_cell(cell, app=app)

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
        # If this is the first cell, and its name is setup, assume that it's
        # the setup cell.
        if len(self._cell_data) == 0 and name == SETUP_CELL_NAME:
            cell_id = CellId_t(SETUP_CELL_NAME)
        else:
            cell_id = self.create_cell_id()

        # - code.split("\n")[1:-1] disregards first and last lines, which are
        #   empty
        # - line[4:] removes leading indent in multiline string
        # - replace(...) unescapes double quotes
        # - rstrip() removes an extra newline
        code = "\n".join(
            [line[4:].replace('\\"', '"') for line in code.split("\n")[1:-1]]
        )

        self.register_cell(
            cell_id=cell_id,
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

    def get_cell_code(self, cell_id: CellId_t) -> Optional[str]:
        """Get the code for a cell by its ID.

        Args:
            cell_id: The ID of the cell

        Returns:
            Optional[str]: The cell's code, or None if the cell doesn't exist
        """
        if cell_id not in self._cell_data:
            return None
        return self._cell_data[cell_id].code

    def get_cell_data(self, cell_id: CellId_t) -> Optional[CellData]:
        """Get the cell data for a specific cell ID.

        Args:
            cell_id: The ID of the cell to get data for

        Returns:
            Optional[CellData]: The cell's data, or None if the cell doesn't exist
        """
        if cell_id not in self._cell_data:
            LOGGER.debug(f"Cell with ID '{cell_id}' not found in cell manager")
            return None
        return self._cell_data[cell_id]

    def get_cell_data_by_name(self, name: str) -> Optional[CellData]:
        """Find a cell ID by its name.

        Args:
            name: The name to search for

        Returns:
            Optional[CellData]: The data of the first cell with matching name,
            or None if no match is found
        """
        for cell_data in self._cell_data.values():
            if cell_data.name.strip("*") == name:
                return cell_data
        return None

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
        new_cell_data: dict[CellId_t, CellData] = {}
        for new_id, old_id in id_mapping.items():
            prev_cell_data = self._cell_data[old_id]
            prev_cell_data.cell_id = new_id
            new_cell_data[new_id] = prev_cell_data

        self._cell_data = new_cell_data

        # Add the new ids to the set, so we don't reuse them in the future
        for _id in sorted_ids:
            self._cell_id_generator.seen_ids.add(_id)

    @property
    def seen_ids(self) -> set[CellId_t]:
        return self._cell_id_generator.seen_ids


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

    # ids that are not in prev_ids but in next_ids
    id_pool = set(next_ids) - set(prev_ids)

    def get_next_available_id(idx: int) -> CellId_t:
        cell_id = next_ids[idx]
        # Use the id from the pool if available
        if cell_id in id_pool:
            id_pool.remove(cell_id)
        elif id_pool:
            # Otherwise just use the next available id
            cell_id = id_pool.pop()
        else:
            # If no ids are available, we could generate a new one
            # but this should never run.
            raise RuntimeError(
                "No available IDs left to assign. This should not happen."
            )
        return cell_id

    def filter_and_backfill() -> list[CellId_t]:
        for idx, _ in enumerate(next_ids):
            if result[idx] is None:
                # If we have a None, we need to fill it with an available ID
                result[idx] = get_next_available_id(idx)
        filtered = [_id for _id in result if _id is not None]
        assert len(filtered) == len(next_codes)
        return filtered

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

    def _hungarian_algorithm(scores: list[list[int]]) -> list[int]:
        """Implements the Hungarian algorithm to find the best matching."""
        score_matrix = [row[:] for row in scores]
        n = len(score_matrix)

        # Step 1: Subtract row minima
        for i in range(n):
            min_value = min(score_matrix[i])
            for j in range(n):
                score_matrix[i][j] -= min_value

        # Step 2: Subtract column minima
        for j in range(n):
            min_value = min(score_matrix[i][j] for i in range(n))
            for i in range(n):
                score_matrix[i][j] -= min_value

        # Step 3: Find initial assignment
        row_assignment = [-1] * n
        col_assignment = [-1] * n

        # Find independent zeros
        for i in range(n):
            for j in range(n):
                if (
                    score_matrix[i][j] == 0
                    and row_assignment[i] == -1
                    and col_assignment[j] == -1
                ):
                    row_assignment[i] = j
                    col_assignment[j] = i

        # Step 4: Improve assignment iteratively
        while True:
            assigned_count = sum(1 for x in row_assignment if x != -1)
            if assigned_count == n:
                break

            # Find minimum uncovered value
            min_uncovered = float("inf")
            for i in range(n):
                for j in range(n):
                    if row_assignment[i] == -1 and col_assignment[j] == -1:
                        min_uncovered = min(min_uncovered, score_matrix[i][j])

            if min_uncovered == float("inf"):
                break

            # Update matrix
            for i in range(n):
                for j in range(n):
                    if row_assignment[i] == -1 and col_assignment[j] == -1:
                        score_matrix[i][j] -= min_uncovered
                    elif row_assignment[i] != -1 and col_assignment[j] != -1:
                        score_matrix[i][j] += min_uncovered

            # Try to find new assignments
            for i in range(n):
                if row_assignment[i] == -1:
                    for j in range(n):
                        if score_matrix[i][j] == 0 and col_assignment[j] == -1:
                            row_assignment[i] = j
                            col_assignment[j] = i
                            break

        # Convert to result format
        result = [-1] * n
        for i in range(n):
            if row_assignment[i] != -1:
                result[row_assignment[i]] = i

        return result

    # 0. Hash matching to capture permutations (dequeue similar hashes)
    # 1. Find the edit distance
    # 2. For replacements, or additions with replacements
    previous_lookup: dict[str, list[CellId_t]] = {}
    for cell_id, code in zip(prev_ids, prev_codes):
        previous_lookup.setdefault(code, []).append(cell_id)

    # covers next is a subset of prev
    result: list[Optional[CellId_t]] = [None] * len(next_codes)
    filled = 0
    for idx, code in enumerate(next_codes):
        if code in previous_lookup:
            # If we have an exact match, use it
            filled += 1
            result[idx] = previous_lookup[code].pop(0)
            if not previous_lookup[code]:
                del previous_lookup[code]

    # If we filled all positions, return the result
    # or if prev is a subset of next, then prev has been dequeued and emptied.
    if filled == len(next_codes) or not previous_lookup:
        return filter_and_backfill()

    # The remaining case is prev ^ next is not empty.
    next_lookup: dict[str, list[CellId_t]] = {}
    for maybe_result, cell_id, code in zip(result, next_ids, next_codes):
        if maybe_result is not None:
            continue
        next_lookup.setdefault(code, []).append(cell_id)

    added_code = list(set(next_lookup.keys()))
    deleted_code = list(set(previous_lookup.keys()))
    next_order: dict[int, list[int]] = {}
    prev_order: dict[int, list[int]] = {}
    offset = 0
    for i, code in enumerate(added_code):
        next_order[i] = [offset + j for j in range(len(next_lookup[code]))]
        offset += len(next_lookup[code])

    offset = 0
    for i, code in enumerate(deleted_code):
        prev_order[i] = [offset + j for j in range(len(previous_lookup[code]))]
        offset += len(previous_lookup[code])

    next_inverse = {code: i for i, code in enumerate(added_code)}
    inverse_order = {idx: i for i, idxs in prev_order.items() for idx in idxs}

    # Pad the scores matrix to ensure it is square
    n = max(len(next_codes) - filled, len(prev_codes) - filled)
    scores = [[0] * n for _ in range(n)]
    for i, code in enumerate(added_code):
        for j, prev_code in enumerate(deleted_code):
            score = similarity_score(prev_code, code)
            for x in next_order[i]:
                for y in prev_order[j]:
                    scores[x][y] = score

    # Use Hungarian algorithm to find the best matching
    matches = _hungarian_algorithm(scores)
    for idx, code in enumerate(next_codes):
        if result[idx] is None:
            match_idx = next_order[next_inverse[code]].pop(0)
            if match_idx != -1:
                result[idx] = previous_lookup[
                    deleted_code[inverse_order[matches[match_idx]]]
                ].pop(0)

    return filter_and_backfill()
