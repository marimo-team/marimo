# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import builtins
from enum import Enum
from typing import TYPE_CHECKING, Optional

from marimo._ast.app import InternalApp
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.visitor import Name
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator

# Constant for easy reuse in tests
HINT_UNPARSABLE = "Cannot parse cell."
HINT_BAD_NAME = (
    "Top level definitions cannot be named 'app', '__name__' or 'generated'"
)
HINT_NOT_SINGLE = "Cell must contain exactly one function definition"
HINT_ORDER_DEPENDENT = (
    "Signature and decorators depend on {} defined out of correct cell order"
)
HINT_HAS_REFS = (
    "Function contains references to variables {} which are not top level."
)
HINT_HAS_CLOSE_REFS = (
    "Function contains references to variables {} which failed to be toplevel."
)


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
        self._name = name
        self._type: TopLevelType = TopLevelType.UNPARSABLE
        self.dependencies: set[Name] = set()
        self._cell: Optional[CellImpl] = None
        self.hint: Optional[str] = None

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
    ) -> None:
        if potential_refs is None:
            potential_refs = set()
        if unresolved is None:
            unresolved = set()

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
        if self.name in ("app", "__generated__", "__name__"):
            self.demote(HINT_BAD_NAME)
            return

        allowed_refs = set(allowed_refs) | {self.name}
        order_dependent_refs = var.unbounded_refs - allowed_refs
        if order_dependent_refs and order_dependent_refs - unresolved:
            self.dependencies = order_dependent_refs
            if not order_dependent_refs - (unresolved | potential_refs):
                self.demote(HINT_ORDER_DEPENDENT.format(self.dependencies))
            else:
                self.demote(HINT_HAS_REFS.format(self.dependencies))
            return

        dependent_refs = var.required_refs - allowed_refs
        if not dependent_refs:
            self.type = TopLevelType.TOPLEVEL
            return

        defined_refs = dependent_refs - potential_refs
        if not (defined_refs):
            self.type = TopLevelType.UNRESOLVED
            self.dependencies = dependent_refs
            return

        self.demote(HINT_HAS_REFS.format(defined_refs))

    def demote(self, hint: str) -> None:
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

        # Track definitions and references
        defs: set[Name] = set()
        refs: set[Name] = set()
        self.allowed_refs: set[Name] = set(toplevel_defs)
        # Run through and get deff + refs, and a naive attempt at resolving cell
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
            if status.is_toplevel:
                self.allowed_refs.add(status.name)

        # Refresh names
        names = [status.name for status in self.statuses]

        self.unshadowed = set(builtins.__dict__.keys()) - defs
        self.allowed_refs.update(self.unshadowed)
        self.used_refs = refs

        # Now toplevel, "allowed" defs have been determined, we can resolve
        # references, and potentially promote cells to toplevel.
        unresolved: set[Name] = set()
        for status in self.statuses:
            if status.is_unresolved or status.is_cell:
                self._statuses[status.type].pop(status.name)
                status.update(self.allowed_refs, unresolved, set(names))
                if status.is_toplevel:
                    self.allowed_refs.add(status.name)
                elif status.is_unresolved:
                    unresolved.add(status.name)
                self._statuses[status.type][status.name] = status

        self._resolve_dependencies()
        # Don't change names of objects that are not toplevel.
        for status in self.cells.values():
            status.name = status._name

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

    @classmethod
    def from_app(cls, app: InternalApp) -> TopLevelExtraction:
        codes = list(app.cell_manager.codes())
        names = list(app.cell_manager.names())
        cell_configs = list(app.cell_manager.configs())

        from marimo._ast.codegen import get_setup_cell

        setup = get_setup_cell(codes, names, cell_configs, True)
        if setup:
            return cls(codes, names, cell_configs, setup.defs)
        return cls(codes, names, cell_configs, set())

    def __iter__(self) -> Iterator[TopLevelStatus]:
        """Iterate over cell statuses"""
        return iter(self.statuses)
