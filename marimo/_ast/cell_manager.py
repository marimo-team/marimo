# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    ParamSpec,
    TypeAlias,
    TypeVar,
)

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
from marimo._ast.parse import fixed_dedent
from marimo._ast.pytest import process_for_pytest
from marimo._messaging.notebook.changes import CreateCell, Transaction
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._schemas.serialization import (
    CellDef,
    SetupCell,
)
from marimo._types.ids import CellId_t
from marimo._utils.cell_matching import match_cell_ids_by_similarity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import FrameType

    from marimo._ast.app import InternalApp

P = ParamSpec("P")
R = TypeVar("R")
Fn: TypeAlias = Callable[P, R]
Cls: TypeAlias = type
Obj: TypeAlias = Cls | Fn[P, R]

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
        self._document = NotebookDocument()
        self._compiled_cells: dict[CellId_t, Cell | None] = {}
        self.prefix = prefix
        self.unparsable = False
        self._cell_id_generator = CellIdGenerator(prefix, seed=42)

    @property
    def document(self) -> NotebookDocument:
        """The underlying NotebookDocument tracking cell-list state."""
        return self._document

    def create_cell_id(self) -> CellId_t:
        """Create a new unique cell ID.

        Returns:
            CellId_t: A new cell ID consisting of the manager's prefix followed by 4 random letters.
        """
        return self._cell_id_generator.create_cell_id()

    def cell_decorator(
        self,
        obj: Obj[P, R] | None,
        column: int | None,
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
        config: CellConfig | None = None,
    ) -> Cell:
        """Registers cells when called through a context block."""
        cell = context_cell_factory(
            cell_id=self.setup_cell_id,
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
        cell_id: CellId_t | None,
        code: str,
        config: CellConfig | None,
        name: str = DEFAULT_CELL_NAME,
        cell: Cell | None = None,
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
        else:
            self._cell_id_generator.seen_ids.add(cell_id)

        resolved_config = config or CellConfig()
        self._document.apply(
            Transaction(
                changes=(
                    CreateCell(
                        cell_id=cell_id,
                        code=code,
                        name=name,
                        config=resolved_config,
                    ),
                ),
                source="cell_manager",
            )
        )
        self._compiled_cells[cell_id] = cell

    def register_ir_cell(
        self, cell_def: CellDef, app: InternalApp | None = None
    ) -> None:
        if isinstance(cell_def, SetupCell):
            cell_id = self.setup_cell_id
        else:
            cell_id = self.create_cell_id()
        filename = app.filename if app is not None else None
        cell_config = CellConfig.from_dict(
            cell_def.options,
        )

        try:
            cell = ir_cell_factory(
                cell_def, cell_id=cell_id, filename=filename
            )
        except SyntaxError:
            self.unparsable = True
            self.register_cell(
                cell_id=cell_id,
                code=cell_def.code,
                config=cell_config,
                name=cell_def.name,
                cell=None,
            )
            return
        cell._cell.configure(cell_config)
        self._register_cell(cell, app=app)

    def register_unparsable_cell(
        self,
        code: str,
        name: str | None,
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
        if len(self._document) == 0 and name == SETUP_CELL_NAME:
            cell_id = self.setup_cell_id
        else:
            cell_id = self.create_cell_id()

        self.register_cell(
            cell_id=cell_id,
            code=fixed_dedent(code).strip(),
            config=cell_config,
            name=name or DEFAULT_CELL_NAME,
            cell=None,
        )

    def ensure_one_cell(self) -> None:
        """Ensure at least one cell exists in the manager.

        If no cells exist, creates an empty cell with default configuration.
        """
        if len(self._document) == 0:
            cell_id = self.create_cell_id()
            self.register_cell(
                cell_id=cell_id,
                code="",
                config=CellConfig(),
            )

    def _synthesize_cell_data(self, nb_cell: NotebookCell) -> CellData:
        """Build a CellData view from a NotebookCell + the compiled sidecar."""
        return CellData(
            cell_id=nb_cell.id,
            code=nb_cell.code,
            name=nb_cell.name,
            config=nb_cell.config,
            cell=self._compiled_cells.get(nb_cell.id),
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
        return self._document.get_cell(cell_id).name

    def names(self) -> Iterable[str]:
        """Get an iterator over all cell names.

        Returns:
            Iterable[str]: Iterator yielding each cell's name
        """
        for nb_cell in self._document._cells:
            yield nb_cell.name

    def codes(self) -> Iterable[str]:
        """Get an iterator over all cell codes.

        Returns:
            Iterable[str]: Iterator yielding each cell's source code
        """
        for nb_cell in self._document._cells:
            yield nb_cell.code

    def code_lookup(self) -> dict[CellId_t, str]:
        """Get a dict for cell codes.

        Returns:
            dict[CellId_t, str]: Dictionary mapping cell to their source code
        """
        return {nb_cell.id: nb_cell.code for nb_cell in self._document._cells}

    def configs(self) -> Iterable[CellConfig]:
        """Get an iterator over all cell configurations.

        Returns:
            Iterable[CellConfig]: Iterator yielding each cell's configuration
        """
        for nb_cell in self._document._cells:
            yield nb_cell.config

    def valid_cells(
        self,
    ) -> Iterable[tuple[CellId_t, Cell]]:
        """Get an iterator over all valid (parsable) cells.

        Returns:
            Iterable[tuple[CellId_t, Cell]]: Iterator yielding tuples of (cell_id, cell)
            for each valid cell
        """
        for nb_cell in self._document._cells:
            cell = self._compiled_cells.get(nb_cell.id)
            if cell is not None:
                yield (nb_cell.id, cell)

    def valid_cell_ids(self) -> Iterable[CellId_t]:
        """Get an iterator over IDs of all valid cells.

        Returns:
            Iterable[CellId_t]: Iterator yielding cell IDs of valid cells
        """
        for nb_cell in self._document._cells:
            if self._compiled_cells.get(nb_cell.id) is not None:
                yield nb_cell.id

    def cell_ids(self) -> Iterable[CellId_t]:
        """Get an iterator over all cell IDs in registration order.

        Returns:
            Iterable[CellId_t]: Iterator yielding all cell IDs
        """
        return self._document.cell_ids

    def has_cell(self, cell_id: CellId_t) -> bool:
        """Check if a cell with the given ID exists.

        Args:
            cell_id: The ID to check

        Returns:
            bool: True if the cell exists, False otherwise
        """
        return cell_id in self._document

    def cells(
        self,
    ) -> Iterable[Cell | None]:
        """Get an iterator over all Cell objects.

        Returns:
            Iterable[Optional[Cell]]: Iterator yielding Cell objects (or None for invalid cells)
        """
        for nb_cell in self._document._cells:
            yield self._compiled_cells.get(nb_cell.id)

    def config_map(self) -> dict[CellId_t, CellConfig]:
        """Get a mapping of cell IDs to their configurations.

        Returns:
            dict[CellId_t, CellConfig]: Dictionary mapping cell IDs to their configurations
        """
        return {
            nb_cell.id: nb_cell.config for nb_cell in self._document._cells
        }

    def cell_data(self) -> Iterable[CellData]:
        """Get an iterator over all cell data.

        Returns:
            Iterable[CellData]: Iterator yielding CellData objects for all cells
        """
        for nb_cell in self._document._cells:
            yield self._synthesize_cell_data(nb_cell)

    def code_map(self) -> dict[CellId_t, str]:
        """Get a mapping of cell IDs to their codes.

        Returns:
            dict[CellId_t, str]: Dictionary mapping cell IDs to their codes
        """
        return {nb_cell.id: nb_cell.code for nb_cell in self._document._cells}

    def cell_data_at(self, cell_id: CellId_t) -> CellData:
        """Get the cell data for a specific cell ID.

        Args:
            cell_id: The ID of the cell to get data for

        Returns:
            CellData: The cell's data

        Raises:
            KeyError: If the cell_id doesn't exist
        """
        return self._synthesize_cell_data(self._document.get_cell(cell_id))

    def get_cell_code(self, cell_id: CellId_t) -> str | None:
        """Get the code for a cell by its ID.

        Args:
            cell_id: The ID of the cell

        Returns:
            Optional[str]: The cell's code, or None if the cell doesn't exist
        """
        nb_cell = self._document.get(cell_id)
        if nb_cell is None:
            return None
        return nb_cell.code

    def get_cell_data(self, cell_id: CellId_t) -> CellData | None:
        """Get the cell data for a specific cell ID.

        Args:
            cell_id: The ID of the cell to get data for

        Returns:
            Optional[CellData]: The cell's data, or None if the cell doesn't exist
        """
        nb_cell = self._document.get(cell_id)
        if nb_cell is None:
            LOGGER.debug(f"Cell with ID '{cell_id}' not found in cell manager")
            return None
        return self._synthesize_cell_data(nb_cell)

    def get_cell_data_by_name(self, name: str) -> CellData | None:
        """Find a cell ID by its name.

        Args:
            name: The name to search for

        Returns:
            Optional[CellData]: The data of the first cell with matching name,
            or None if no match is found
        """
        for nb_cell in self._document._cells:
            if nb_cell.name.strip("*") == name:
                return self._synthesize_cell_data(nb_cell)
        return None

    def get_cell_id_by_code(self, code: str) -> CellId_t | None:
        """Find a cell ID by its code content.

        Args:
            code: The code to search for

        Returns:
            Optional[CellId_t]: The ID of the first cell with matching code,
            or None if no match is found
        """
        for nb_cell in self._document._cells:
            if nb_cell.code == code:
                return nb_cell.id
        return None

    def _replace_state_from(self, other: CellManager) -> None:
        """Overwrite this manager's content with ``other``'s, in place.

        Identity-preserving substitute for ``self = other``: the
        underlying ``NotebookDocument`` instance and the
        ``_compiled_cells`` dict instance are kept; only their contents
        are replaced. Any object holding a reference to this manager —
        most notably the owning ``Session`` (which holds
        ``cell_manager.document`` as ``session.document``) — continues
        to see live state without rebinding.

        ``unparsable`` is copied. ``_cell_id_generator.seen_ids`` is
        unioned (never narrowed) so we don't recycle an id seen
        previously even if it's gone from ``other``.

        Transitional helper: cell-list bulk-replace bypasses
        ``NotebookDocument.apply``. Goes away once full-document
        rebuilds are expressed as diff Transactions.
        """
        self._document._replace_cells(list(other._document._cells))
        self._compiled_cells.clear()
        self._compiled_cells.update(other._compiled_cells)
        self.unparsable = other.unparsable
        self._cell_id_generator.seen_ids |= other._cell_id_generator.seen_ids

    def sort_cell_ids_by_similarity(
        self, prev_cell_manager: CellManager
    ) -> None:
        """Sort cell IDs by similarity to the current cell manager.

        This mutates the current cell manager.
        """
        prev_codes = prev_cell_manager.code_lookup()
        current_codes = self.code_lookup()
        # match_cell_ids_by_similarity returns {new_id: old_id};
        # _rekey expects {old_id: new_id}.
        id_mapping = match_cell_ids_by_similarity(prev_codes, current_codes)
        rekey = {old_id: new_id for new_id, old_id in id_mapping.items()}

        self._document._rekey(rekey)
        self._compiled_cells = {
            rekey.get(old_id, old_id): cell
            for old_id, cell in self._compiled_cells.items()
        }

        for new_id in id_mapping:
            self._cell_id_generator.seen_ids.add(new_id)

    @property
    def seen_ids(self) -> set[CellId_t]:
        return self._cell_id_generator.seen_ids

    @property
    def setup_cell_id(self) -> CellId_t:
        return CellId_t(self.prefix + SETUP_CELL_NAME)
