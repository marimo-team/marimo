# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Optional

from textwrap import dedent

from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    ClassCell,
    FunctionCell,
    Header,
    NotebookSerialization,
    UnparsableCell,
    Violation,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class MarimoFileError(Exception):
    pass


class _Extractor:
    def __init__(self, filename: Optional[str]):
        self.contents = None
        if filename is not None:
            with open(filename, encoding="utf-8") as f:
                self.contents = f.read().strip()

        self.lines = self.contents.splitlines() if self.contents else []

    def extract_from_offsets(
        self, lineno, col_offset, end_lineno, end_col_offset
    ) -> str:
        if lineno == end_lineno:
            return self.lines[lineno][col_offset:end_col_offset]
        if lineno + 1 == end_lineno:
            return dedent(
                "\n".join(
                    [
                        self.lines[lineno][col_offset:],
                        self.lines[end_lineno][:end_col_offset],
                    ]
                )
            )
        return dedent(
            "\n".join(
                [
                    self.lines[lineno][col_offset:],
                    "\n".join(self.lines[lineno + 1 : end_lineno]),
                    self.lines[end_lineno][:end_col_offset],
                ]
            )
        )

    def extract_from_code(self, node: ast.stmt) -> str:
        return self.extract_from_offsets(
            node.lineno, node.col_offset, node.end_lineno, node.end_col_offset
        )

    def to_cell(self, node: ast.stmt) -> CellDef:
        """Convert an AST node to a CellDef."""
        if isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            decorator = node.decorator_list[0]
            # switch on app.cell vs app.function
            if isinstance(decorator, ast.Call):
                attribute = decorator.func.attr
                kwargs, _violations = _eval_kwargs(decorator.keywords)
            elif isinstance(decorator, ast.Attribute):
                attribute = decorator.attr
                kwargs, _violations = {}, []
            else:
                raise ValueError("Decorator is not an attribute.")

            if attribute == "cell":
                # node.decorator_list.pop(0)
                # Check how much to increment based on the decorator
                # ast.increment_lineno(node)
                return CellDef(
                    code=self.extract_from_code(node),
                    options=kwargs,
                    _ast=node,
                )

            if attribute == "function":
                return FunctionCell(
                    # scrub the leading decorator
                    code=self.extract_from_code(node),
                    _ast=node,
                    options=kwargs,
                )
            elif attribute == "class_definition":
                return ClassCell(
                    # scrub the leading decorator
                    code=self.extract_from_code(node),
                    _ast=node,
                    options=kwargs,
                )

            raise ValueError(f"Unsupported cell type. {attribute}")
        elif isinstance(node, ast.Call):
            # captures app._unparsable_cell("str", **kwargs)"
            if not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "_unparsable_cell"
            ):
                raise ValueError("Not an unparsable cell.")

            _kwargs, _violations = _eval_kwargs(node.keywords)
            return UnparsableCell(
                code=self.extract_from_code(node),
                options=_kwargs,
                _ast=node,
            )


def _maybe_version(node: ast.stmt) -> Optional[str]:
    # Assign(
    #   targets=[
    #     Name(id='__generated_with', ctx=Store())],
    #   value=Constant(value=...)
    # )
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        if isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "__generated_with":
                if isinstance(node.value, ast.Constant):
                    return node.value.value


def _gen_stack(iterable) -> Generator[ast.stmt, ast.stmt, None]:
    """A generator that yields items from the iterable."""
    for item in iterable:
        value = yield item
        if value is not None:
            yield value
    while True:
        yield None
        if value is not None:
            yield value


def _eval_kwargs(keywords: list[ast.keyword]) -> dict[str, Any]:
    """Convert a list of keyword arguments to a dictionary."""
    kwargs = {}
    violations = []
    for kw in keywords:
        # Only accept Constants
        if isinstance(kw.value, ast.Constant):
            kwargs[kw.arg] = kw.value.value
        else:
            violations.append(
                Violation(
                    "Unexpected value for keyword argument",
                    lineno=kw.lineno,
                    col_offset=kw.col_offset,
                )
            )
    return kwargs, violations


def is_marimo_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.Import) and node.names[0].name == "marimo"


def is_string(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def is_app_def(node: ast.stmt) -> bool:
    # Assign(
    #   targets=[
    #     Name(id='app', ctx=Store())],
    #   value=Call(
    #     func=Attribute(
    #       value=Name(id='marimo', ctx=Load()),
    #       attr='App',
    #       ctx=Load()),
    #     args=[],
    #     keywords=[
    #       keyword(
    #         arg=...,
    #         value=Constant(value=...)),
    #     ]
    #   )
    # )

    # A bit obnoxious as a huge conditional, but also better for line coverage.
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "app"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "marimo"
        and node.value.func.attr == "App"
    )


def is_cell_decorator(decorator: ast.stmt) -> bool:
    if isinstance(decorator, ast.Attribute):
        return (
            isinstance(decorator.value, ast.Name)
            and decorator.value.id == "app"
            and decorator.attr in ("cell", "function", "class_definition")
        )
    elif isinstance(decorator, ast.Call):
        return is_cell_decorator(decorator.func)
    return False


def is_unparsable_cell(node: ast.stmt) -> bool:
    # captures app._unparsable_cell("str", **kwargs)"
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "app"
        and node.func.attr == "_unparsable_cell"
        and len(node.args) == 1
    )


def is_body_cell(node: ast.stmt) -> bool:
    # should have decorator @app.cell, @app.function, @app.class_definition
    return (
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and node.decorator_list
        and is_cell_decorator(node.decorator_list[0])
    )


def _is_setup_call(node: ast.stmt) -> bool:
    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == "app"
            and node.attr == "setup"
        )
    elif isinstance(node, ast.Call):
        return _is_setup_call(node.func)
    return False


def is_setup_cell(node: ast.stmt) -> bool:
    return (
        isinstance(node, (ast.AsyncWith, ast.With))
        and len(node.items) == 1
        and _is_setup_call(node.items[0].context_expr)
    )


def is_cell(node: ast.stmt) -> bool:
    return (
        is_setup_cell(node) or is_body_cell(node) or is_unparsable_cell(node)
    )


def is_run_guard(node: ast.stmt) -> bool:
    return node == ast.parse('if __name__ == "__main__": app.run()').body[0]


def parse_notebook(filename: str) -> Optional[NotebookSerialization]:
    extractor = _Extractor(filename)
    if not extractor.contents:
        return None

    body = _gen_stack(ast.parse(extractor.contents).body)

    header = None
    import_node = None
    version = None
    app = None
    cells = []

    # TODO(dmadisetti): Expand lint system github/marimo-team/marimo#1543
    violations: list[Violation] = []

    # header? = (docstring | comments)*
    while node := next(body):
        # Just string, comments are stripped
        if not is_string(node):
            break

    if not node:
        # TODO(dmadisetti): Raise an error or add severity to violations?
        raise MarimoFileError("File only contains a header.")

    header = Header(
        lineno=0,
        col_offset=0,
        end_lineno=node.lineno,
        end_col_offset=node.col_offset,
        value=extractor.extract_from_offsets(
            0, 0, node.lineno, node.col_offset
        ),
    )

    # app = import marimo + __generated_with + App(kwargs*)
    if not is_marimo_import(node):
        violations.append(
            Violation(
                "Unexpected statement (expected marimo import)",
                lineno=node.lineno,
            )
        )
        # Attempt to find import statement
        while node := next(body):
            if is_marimo_import(node):
                import_node = node
                break
    else:
        import_node = node

    if not import_node:
        raise MarimoFileError("`marimo` import expected.")

    # __generated_with not being correctly set should not break marimo.
    node = next(body)
    version = _maybe_version(node)
    if not version:
        # Put whatever this was, back on the stack
        body.send(node)

        violations.append(
            Violation(
                "Expected `__generated_with` assigment for marimo version number.",
                lineno=node.lineno,
            )
        )

    while node := next(body):
        if is_app_def(node):
            _kwargs, _violations = _eval_kwargs(node.value.keywords)
            violations.extend(violations)
            app = AppInstantiation(
                options=_kwargs,
            )
            break
        violations.append(
            Violation(
                "Unexpected statement, expected App initialization.",
                node.lineno,
            )
        )

    if not app:
        raise MarimoFileError("`marimo.App` definition expected.")

    # setup? = Async?With(kwargs*, stmt*)
    # Check for cell
    while node := next(body):
        if is_cell(node):
            break

    if is_cell(node):
        cells.append(extractor.to_cell(node))
    elif is_run_guard(node):
        return NotebookSerialization(
            header=header, version=version, app=app, violations=violations
        )

    # Continue with remainder of body
    while node := next(body):
        if is_body_cell(node):
            cells.append(extractor.to_cell(node))
        elif is_run_guard(node):
            return NotebookSerialization(
                header=header,
                version=version,
                app=app,
                cells=cells,
                violations=violations,
            )
        else:
            violations.append(
                Violation(
                    "Unexpected statement, expected body cell definition.",
                    node.lineno,
                )
            )

    # Expected a run guard, but that's OK.
    violations.append(Violation("Expected run guard statement"))
    return NotebookSerialization(
        header=header,
        version=version,
        app=app,
        cells=cells,
        violations=violations,
    )
