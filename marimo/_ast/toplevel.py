# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import token as token_types
from enum import Enum
from io import BytesIO
from tokenize import tokenize
from typing import TYPE_CHECKING, Literal, Optional, Union, get_args

from marimo._ast.app import InternalApp
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.names import (
    DEFAULT_CELL_NAME,
    SETUP_CELL_NAME,
    TOPLEVEL_CELL_PREFIX,
)
from marimo._ast.variables import BUILTINS
from marimo._ast.visitor import Name, VariableData
from marimo._runtime.dataflow import DirectedGraph
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator

# Constant for easy reuse in tests.
# The formatting here affects how the error is rendered in the frontend.
# This is a hack but fine for now ...
TopLevelInvalidHints = Literal[
    "Cannot parse cell.",
    (
        "Reusable definitions cannot be named 'app', '__name__' or "
        "'__generated_with'"
    ),
    "Cell must contain exactly one function definition",
    "Signature and decorators depend on {} defined out of correct cell order",
    "This function depends on variables defined by other cells:\n\n{}\n\nTo make this function importable from other Python modules,\nmove these variables to the setup cell.",
    "Function contains references to variables {} which were unable to become reusable.",
    "Cell cannot contain non-indented trailing comments.",
]
(
    HINT_UNPARSABLE,
    HINT_BAD_NAME,
    HINT_NOT_SINGLE,
    HINT_ORDER_DEPENDENT,
    HINT_HAS_REFS,
    HINT_HAS_CLOSE_REFS,
    HINT_HAS_COMMENT,
) = get_args(TopLevelInvalidHints)

TopLevelHints = Union[Literal["Valid"], TopLevelInvalidHints]
# Fancy typing caused an issue, so just set the value explicitly.
HINT_VALID: Literal["Valid"] = "Valid"


def has_trailing_comment(code: str) -> bool:
    # Requires tokenization because multiline strings can start a line with #.
    tokens = tokenize(BytesIO(code.strip().encode("utf-8")).readline)
    for token in reversed(list(tokens)):
        if token.type in (
            token_types.ENDMARKER,
            token_types.NEWLINE,
            token_types.NL,
            token_types.INDENT,
            token_types.DEDENT,
            token_types.ENCODING,
        ):
            continue
        return token.type == token_types.COMMENT and token.start[1] == 0
    return False


class TopLevelType(Enum):
    CELL = "cell"
    TOPLEVEL = "toplevel"
    UNPARSABLE = "unparsable"
    UNRESOLVED = "unresolved"


class TopLevelStatus:
    """Status of a cell during serialization"""

    def __init__(
        self,
        cell_id: CellId_t,
        code: str,
        name: Name,
        cell_config: CellConfig,
        allowed_refs: set[Name],
    ):
        self.cell_id = cell_id
        self.name = name
        self.previous_name = name
        self._type: TopLevelType = TopLevelType.UNPARSABLE
        self.dependencies: set[Name] = set()
        self._cell: Optional[CellImpl] = None
        self.hint: Optional[TopLevelHints] = None

        self.code = code
        self.cell_config = cell_config

        self.update(allowed_refs)

    @classmethod
    def from_cell(
        cls, cell: CellImpl, allowed_refs: set[Name]
    ) -> TopLevelStatus:
        return cls(cell.cell_id, cell.code, "_", CellConfig(), allowed_refs)

    def update(
        self,
        allowed_refs: set[Name],
        unresolved: set[Name] | None = None,
        potential_refs: set[Name] | None = None,
        toplevel: set[Name] | None = None,
    ) -> None:
        if potential_refs is None:
            potential_refs = set()
        if unresolved is None:
            unresolved = set()
        if toplevel is None:
            toplevel = set()

        if self._cell is None:
            try:
                self._cell = compile_cell(
                    self.code, cell_id=self.cell_id
                ).configure(self.cell_config)
            except SyntaxError:
                # Keep default
                self.type = TopLevelType.UNPARSABLE
                self.hint = HINT_UNPARSABLE
                return

        # Check that def matches the single definition
        var = self._cell.toplevel_variable
        if var is None:
            self.demote(HINT_NOT_SINGLE)
            return

        (self.name,) = self._cell.defs
        if self.name in ("app", "__generated_with", "__name__"):
            self.demote(HINT_BAD_NAME)
            return

        # Trailing comments are not allowed, since no easy way to recapture
        # them.
        if has_trailing_comment(self.code):
            self.demote(HINT_HAS_COMMENT)
            return

        allowed_refs = set(allowed_refs) | {self.name, "_lambda"}
        order_dependent_refs = var.unbounded_refs - allowed_refs

        if order_dependent_refs and order_dependent_refs - unresolved:
            self.dependencies = order_dependent_refs
            if not order_dependent_refs - (unresolved | potential_refs):
                self.demote(HINT_ORDER_DEPENDENT.format(self.dependencies))
            else:
                self.demote(HINT_HAS_REFS.format(self.dependencies))
            return

        dependent_refs = self._cell.refs - (allowed_refs | toplevel)
        if not dependent_refs:
            self.type = TopLevelType.TOPLEVEL
            self.hint = HINT_VALID
            return

        defined_refs = dependent_refs - potential_refs
        if not (defined_refs):
            self.type = TopLevelType.UNRESOLVED
            self.dependencies = dependent_refs
            return

        self.demote(HINT_HAS_REFS.format(defined_refs))

    def demote(self, hint: TopLevelInvalidHints) -> None:
        self.type = TopLevelType.CELL
        self.hint = hint

    @property
    def defs(self) -> set[Name]:
        if self._cell is None:
            return set()
        return self._cell.defs

    @property
    def refs(self) -> set[Name]:
        if self._cell is None:
            return set()
        return self._cell.refs

    @property
    def type(self) -> TopLevelType:
        return self._type

    @type.setter
    def type(self, value: TopLevelType) -> None:
        self._type = value
        self.hint = None

    @property
    def is_toplevel(self) -> bool:
        return self.type == TopLevelType.TOPLEVEL

    @property
    def is_cell(self) -> bool:
        return self.type == TopLevelType.CELL

    @property
    def is_unresolved(self) -> bool:
        return self.type == TopLevelType.UNRESOLVED

    @property
    def is_unparsable(self) -> bool:
        return self.type == TopLevelType.UNPARSABLE


class TopLevelExtraction:
    """Graph representation of cells for serialization"""

    def __init__(
        self,
        codes: list[str],
        names: list[str],
        cell_configs: list[CellConfig],
        toplevel_defs: set[Name],
    ):
        self.statuses: list[TopLevelStatus] = []

        # Track resolution status
        self.unparsable: dict[Name, TopLevelStatus] = {}
        self.toplevel: dict[Name, TopLevelStatus] = {}
        self.unresolved: dict[Name, TopLevelStatus] = {}
        self.cells: dict[Name, TopLevelStatus] = {}
        self._statuses: dict[TopLevelType, dict[Name, TopLevelStatus]] = {
            TopLevelType.UNPARSABLE: self.unparsable,
            TopLevelType.TOPLEVEL: self.toplevel,
            TopLevelType.UNRESOLVED: self.unresolved,
            TopLevelType.CELL: self.cells,
        }
        self.collection: set[TopLevelStatus] = set({})

        # Track definitions and references
        defs: set[Name] = set()
        refs: set[Name] = set()
        self.allowed_refs: set[Name] = set(toplevel_defs)
        self._variables: Optional[dict[Name, VariableData]] = None
        # Run through and get defs + refs, and a naive attempt at resolving cell
        # status.
        for idx, (code, name, config) in enumerate(
            zip(codes, names, cell_configs)
        ):
            status = TopLevelStatus(
                CellId_t(str(idx)), code, name, config, self.allowed_refs
            )
            self._statuses[status.type][status.name] = status

            self.statuses.append(status)
            if not status.is_unparsable:
                defs.update(status.defs)
                refs.update(status.refs)
            self.collection.add(status)

        # Refresh names
        potential_refs = set(
            [status.name for status in self.statuses if not status.is_toplevel]
        )

        self.unshadowed = BUILTINS - defs
        self.allowed_refs.update(self.unshadowed)
        self.used_refs = refs

        # Now toplevel, "allowed" defs have been determined, we can resolve
        # references, and potentially promote cells to toplevel.
        unresolved: set[Name] = set()
        for status in self.statuses:
            if status.is_unresolved or status.is_cell:
                self._statuses[status.type].pop(status.name)
                status.update(
                    self.allowed_refs,
                    unresolved,
                    potential_refs,
                    set(self.toplevel.keys()),
                )
                if status.is_toplevel:
                    self.allowed_refs.add(status.name)
                elif status.is_unresolved:
                    unresolved.add(status.name)
                self._statuses[status.type][status.name] = status
            else:
                self.allowed_refs.add(status.name)

        self._resolve_dependencies()
        # Don't change names of objects that are not toplevel.
        for status in self.cells.values():
            status.name = status.previous_name
            # For something that used to be top level, revert to default name.
            if status.name.startswith(TOPLEVEL_CELL_PREFIX):
                status.name = DEFAULT_CELL_NAME
        # Set the hint of all valid cells to HINT_VALID
        for status in self.toplevel.values():
            status.hint = HINT_VALID

    def _resolve_dependencies(self) -> None:
        """Resolve the dependencies of unresolved cells"""
        visited: dict[Name, bool] = {}

        def resolve(name: Name) -> bool:
            """Recursively resolve dependencies"""
            # Already processed
            if name not in self.unresolved:
                if name in visited:
                    return visited[name]
                elif name in self.toplevel:
                    return True
                elif name in self.cells or name in self.unparsable:
                    return False
                # We are in a cycle. It's safe to serialize, but marimo will
                # throw an error if running directly. Note, that in library
                # form, multi-recursion is still supported (since it's just raw
                # python).
                return True

            status = self.unresolved.pop(name)
            refs = status.refs

            # Check if all dependencies are resolved
            resolved = True
            invalid = set()
            for ref in refs:
                if not resolve(ref):
                    resolved = False
                    invalid.add(ref)

            if resolved:
                # All dependencies resolved, mark as top-level
                status.type = TopLevelType.TOPLEVEL
                self.allowed_refs.add(name)
            else:
                # Could not resolve all dependencies, mark as cell
                status.demote(HINT_HAS_CLOSE_REFS.format(invalid))
            self._statuses[status.type][name] = status

            visited[name] = resolved
            return resolved

        # Try to resolve all unresolved cells
        names_to_resolve = list(self.unresolved.keys())
        for name in names_to_resolve:
            if name in self.unresolved:
                _ = resolve(name)
        assert not self.unresolved

    @property
    def variables(self) -> dict[Name, VariableData]:
        # Grabs all initial variable data from cells for use in annotations.
        if self._variables is not None:
            return self._variables
        variables = {}

        for status in self.collection:
            if status._cell:
                variables.update(status._cell.init_variable_data)
        for var, status in self.toplevel.items():
            if status._cell:
                toplevel_variable = status._cell.toplevel_variable
                if toplevel_variable:
                    variables[var] = toplevel_variable
        self._variables = variables
        return variables

    @classmethod
    def from_graph(
        cls,
        cell: CellImpl,
        graph: DirectedGraph,
    ) -> TopLevelExtraction:
        ancestors = graph.ancestors(cell.cell_id)
        deps = {cid: graph.cells[cid] for cid in ancestors}
        setup_id = CellId_t(SETUP_CELL_NAME)
        setup = graph.cells.get(setup_id)
        setup = graph.cells.get(setup_id)
        deps.pop(setup_id, None)

        # TODO: Technically, order does matter incase there is a type definition
        # or decorator.
        path = list(deps.values()) + [cell]
        return cls.from_cells(path, setup=setup)

    @classmethod
    def from_cells(
        cls, cells: list[CellImpl], setup: Optional[CellImpl] = None
    ) -> TopLevelExtraction:
        codes = [cell.code for cell in cells]
        names = ["_" for _ in cells]
        cell_configs = [cell.config for cell in cells]

        if setup:
            return cls(codes, names, cell_configs, setup.defs)
        return cls(codes, names, cell_configs, set())

    @classmethod
    def from_app(cls, app: InternalApp) -> TopLevelExtraction:
        codes = list(app.cell_manager.codes())
        names = list(app.cell_manager.names())
        cell_configs = list(app.cell_manager.configs())

        from marimo._ast.codegen import pop_setup_cell

        setup = pop_setup_cell(codes, names, cell_configs)
        if setup:
            return cls(codes, names, cell_configs, setup.defs)
        return cls(codes, names, cell_configs, set())

    def __iter__(self) -> Iterator[TopLevelStatus]:
        """Iterate over cell statuses"""
        return iter(self.statuses)
