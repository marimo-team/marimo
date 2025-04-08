# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.names import DEFAULT_CELL_NAME

if TYPE_CHECKING:
    import ast

    from typing_extensions import TypeAlias


@dataclass
class Node:
    """
    Loosely mirror the python ast statement nodes:
        github:python/cpython/Include/internal/pycore_ast.h#L196
    """

    lineno: int = 0
    col_offset: int = 0
    end_lineno: int = 0
    end_col_offset: int = 0


@dataclass
class Header(Node):
    value: str = ""


@dataclass
class AppInstantiation(Node):
    # NB. differs from InternalApp and App, because this is what's directly read
    # from the notebook.
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class CellDef(Node):
    code: str = ""
    name: str = DEFAULT_CELL_NAME
    options: dict[str, Any] = field(default_factory=dict)

    _ast: Optional[ast.stmt] = None

    def __post_init__(self) -> None:
        if self._ast:
            self.lineno = self._ast.lineno if self.lineno == 0 else self.lineno
            self.col_offset = (
                self._ast.col_offset
                if self.col_offset == 0
                else self.col_offset
            )
            self.end_lineno = (
                self._ast.end_lineno
                if self.end_lineno == 0 and self._ast.end_lineno
                else self.end_lineno
            )
            self.end_col_offset = (
                self._ast.end_col_offset
                if self.end_col_offset == 0 and self._ast.end_col_offset
                else self.end_col_offset
            )
            self.name = getattr(self._ast, "name", DEFAULT_CELL_NAME)


class SetupCell(CellDef): ...


class FunctionCell(CellDef): ...


class ClassCell(CellDef): ...


class UnparsableCell(CellDef): ...


@dataclass
class Violation:
    """
    "Violation" is borrowed from ruff's internal representation.
    A bit harsh sounding, but reasonable.

    Essentially a stub for now:
     - Potentially move to marimo/_lint
     - Consider subclassing to hardcoded descriptions
     - Consider violation ID (e.g mo-0001)
    """

    description: str
    lineno: int = 0
    col_offset: int = 0


@dataclass(frozen=True)
class NotebookSerializationV1:
    """
    The expectation of a notebook structure is as follows:
        notebook = header? + app + setup? + cells* + run_guard
        header = (docstring | comments)*
        app = import marimo + __generated_with + App(kwargs*)
        cells = cell | function | class_definition | unparsable
        setup = Async?With(kwargs*, stmt*)
        cell = Async?Function(kwargs*, stmt*, @cell)
        function = Async?Function(kwargs*, stmt*, @function + decorators*)
        class_definition = ClassDef(kwargs*, stmt*, @class_definition + decorators*)
        unparsable = app._unparsable_cell(code, kwargs*)
        run_guard = if __name__ == "__main__": app.run()

    This is meant to be a representation of the notebook as extracted directly
    from a script
    """

    app: AppInstantiation
    header: Optional[Header] = None
    version: Optional[str] = None
    cells: list[CellDef] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    valid: bool = True


NotebookSerialization: TypeAlias = NotebookSerializationV1


VERSION = "1"
