# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import ast
import io
import token as token_types
from pathlib import Path
from textwrap import dedent
from tokenize import TokenInfo, tokenize
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
)

from marimo._ast.names import DEFAULT_CELL_NAME, SETUP_CELL_NAME
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    ClassCell,
    FunctionCell,
    Header,
    NotebookSerialization,
    SetupCell,
    UnparsableCell,
    Violation,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from typing_extensions import TypeAlias


FnNode: TypeAlias = Union[ast.FunctionDef, ast.AsyncFunctionDef]
CellNode: TypeAlias = Union[FnNode, ast.ClassDef]
Node: TypeAlias = Union[ast.stmt, ast.expr]


V = TypeVar("V")
U = TypeVar("U")


class MarimoFileError(Exception):
    pass


class Extractor:
    """Helper to extract AST nodes to schema/serialization ir."""

    @staticmethod
    def from_file(filename: Union[str, Path]) -> Extractor:
        return Extractor(contents=Path(filename).read_text(encoding="utf-8"))

    def __init__(self, contents: str):
        self.contents = contents.strip()
        self.lines = self.contents.splitlines() if self.contents else []

    def extract_from_offsets(
        self,
        lineno: int,
        col_offset: int,
        end_lineno: int,
        end_col_offset: Optional[int],
    ) -> str:
        if lineno == end_lineno:
            return self.lines[lineno][col_offset:end_col_offset]
        if lineno + 1 == end_lineno:
            return "\n".join(
                [
                    self.lines[lineno][col_offset:],
                    self.lines[end_lineno][:end_col_offset],
                ]
            )
        return "\n".join(
            [
                self.lines[lineno][col_offset:],
                "\n".join(self.lines[lineno + 1 : end_lineno]),
                self.lines[end_lineno][:end_col_offset],
            ]
        )

    def extract_from_code(self, node: Node) -> str:
        # NB. Ast line reference and col index is on a 1-indexed basis.
        lineno = node.lineno
        col_offset = node.col_offset

        if hasattr(node, "decorator_list"):
            # From the ast, having a decorator list means we are either a
            # function or a class.
            assert isinstance(
                node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)
            )

            # Scrub past the decorator + 1, lineno 1 index -1
            if (
                len(node.decorator_list)
                and (decorator := get_valid_decorator(node))  # type: ignore
            ):
                lineno = _none_to_0(decorator.end_lineno)
                col_offset = decorator.col_offset - 1
            else:
                lineno -= 1

        code = self.extract_from_offsets(
            lineno,
            col_offset,
            _none_to_0(node.end_lineno) - 1,
            _none_to_0(node.end_col_offset),
        )
        return dedent(code)

    def to_cell_def(self, node: FnNode, kwargs: dict[str, Any]) -> CellDef:
        # A general note on the apparent brittleness of this code:
        #    - Ast line reference and col index is on a 1-indexed basis
        #    - Multiline statements need to be accounted for
        #    - Painstaking testing can be found in test/_ast/test_{load, parse}

        function_code = self.extract_from_code(node)
        lineno_offset, col_offset = extract_offsets_post_colon(
            function_code,
            block_start="def",
        )
        start_lineno = node.lineno + lineno_offset

        end_lineno = _none_to_0(node.end_lineno)
        end_col_offset = node.end_col_offset
        assert len(node.body) > 0
        if node.lineno - node.body[0].lineno == 0:
            # Quirk where the ellipse token seems to have a line index at
            # the end of the dots ...<
            if isinstance(getattr(node.body[0], "value", None), ast.Ellipsis):
                col_offset += node.body[0].col_offset - 3
            else:
                col_offset += node.body[0].col_offset - 1
        else:
            col_offset = 0

        has_return = isinstance(node.body[-1], ast.Return)
        single_line = node.lineno - node.body[-1].lineno == 0
        if has_return:
            # we need to adjust for the trailing return statement
            # which is not included in the function body
            if len(node.body) > 1:
                end_lineno = max(
                    _none_to_0(node.body[-2].end_lineno),
                    node.body[-1].lineno - 1,
                )
                end_col_offset = len(self.lines[end_lineno - 1]) + 1
                if node.body[-1].end_lineno == end_lineno:
                    end_lineno = node.body[-1].lineno
                    end_col_offset = node.body[-1].col_offset

            # We're in the case where we have something like
            # @app.cell
            # def foo():
            #   # Just comments
            #   return
            else:
                # If we are on the same line as the return statement,
                # just return a blank cell.
                if start_lineno == node.body[0].lineno:
                    return CellDef(
                        code="",
                        options=kwargs,
                        lineno=start_lineno,
                        col_offset=node.col_offset + col_offset,
                        end_lineno=start_lineno,
                        end_col_offset=len(self.lines[-1]),
                        name=getattr(node, "name", DEFAULT_CELL_NAME),
                    )
                else:
                    end_lineno = node.body[-1].lineno - 1
                    end_col_offset = None

        # NB. node.[end_]lineno only captures the starting line of the
        # captured node, same with col_offset.
        # If the node spans multiple lines, then we need to adjust these
        # positions such that _all_ relevant text is captured.
        cell_code = self.extract_from_offsets(
            lineno=start_lineno - 1,
            col_offset=col_offset,
            end_lineno=end_lineno - 1,
            end_col_offset=end_col_offset,
        )

        # NB: Feels pretty hacky, would love if someone had a suggestion for this
        # But the only other better way (I can see) is to drop down to the
        # toeknizer lever and handle it there + handle particular edge
        # cases.
        #
        # If the last value is not a return statement, we need to grab
        # trailing comments.
        if not has_return and not single_line:
            # Determine leading spaces
            leading_spaces = len(cell_code) - len(cell_code.lstrip())
            indent = cell_code[:leading_spaces]

            # Attempt to keep adding lines, and ensure it dedents to the correct
            # level
            new_end = end_lineno - 1
            for new_end in range(end_lineno, len(self.lines)):
                if not self.lines[new_end].strip() or self.lines[
                    new_end
                ].startswith(indent):
                    end_col_offset = len(self.lines[new_end])
                    continue
                new_end -= 1
                break
            if new_end > end_lineno:
                cell_code += "\n".join(
                    self.lines[end_lineno : new_end + 1]
                ).rstrip()
                end_lineno = new_end - 1

        if end_col_offset is None:
            end_col_offset = 0

        # Line positioning here is still consequential for correct stack tracing
        # produced in _ast.compiler.
        return CellDef(
            code=dedent(cell_code),
            options=kwargs,
            lineno=start_lineno - 1,
            col_offset=node.col_offset + col_offset,
            end_lineno=_none_to_0(node.end_lineno) + end_lineno,
            end_col_offset=_none_to_0(node.end_col_offset) + end_col_offset,
            name=getattr(node, "name", DEFAULT_CELL_NAME),
        )

    def to_setup_cell(self, node: Node) -> SetupCell:
        kwargs, _violations = _maybe_kwargs(node.items[0].context_expr)  # type: ignore
        code = self.extract_from_code(node)
        code = dedent(code)
        if code.endswith("\npass"):
            code = code[: -len("\npass")]
        return SetupCell(
            code=code,
            options=kwargs,
            lineno=node.lineno,
            col_offset=node.col_offset,
            end_lineno=max(node.lineno, _none_to_0(node.end_lineno)),
            end_col_offset=_none_to_0(node.end_col_offset),
            name=SETUP_CELL_NAME,
        )

    def to_cell(self, node: Node, attribute: Optional[str] = None) -> CellDef:
        """Convert an AST node to a CellDef."""
        if isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            decorator = get_valid_decorator(node)
            kwargs, _violations = _maybe_kwargs(decorator)
            if attribute is None and decorator is not None:
                if isinstance(decorator, ast.Call):
                    if not hasattr(decorator.func, "attr"):
                        raise MarimoFileError(
                            "Invalid decorator, expected form `@app.fn`"
                        )
                    attribute = decorator.func.attr
                else:
                    attribute = decorator.attr

            # switch on app.cell vs app.function
            if attribute == "cell":
                assert isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ), "@app.cell cannot be used on classes."
                return self.to_cell_def(node, kwargs)
            cell_types: dict[Optional[str], type[CellDef]] = {
                "function": FunctionCell,
                "class_definition": ClassCell,
            }
            cell_type = cell_types.get(attribute, None)
            if cell_type is not None:
                return cell_type(
                    code=self.extract_from_code(node),
                    _ast=node,
                    options=kwargs,
                )

            raise MarimoFileError(f"Unsupported cell type. {attribute}")
        elif is_unparsable_cell(node):
            # These are all captured by is_unparsable_cell
            # but mypy is struggling.
            kwargs, _violations = _eval_kwargs(node.value.keywords)  # type: ignore
            return UnparsableCell(
                code=node.value.args[0].value,  # type: ignore
                options=kwargs,
                _ast=node,
            )

        raise MarimoFileError(
            "Unexpected node type for cell extraction. "
            "Please report this issue to the Marimo team with "
            "your code if possible: "
            "github.com/marimo-team/marimo/issues"
        )


class ParseResult(Generic[V]):
    """Helper class to bundle "violations" and results"""

    __slots__ = ("_value", "_violations")

    def __init__(
        self,
        value: V | None = None,
        violations: list[Violation] | None = None,
    ) -> None:
        self._value = value
        self._violations = []
        if violations is not None:
            self._violations = violations

    @property
    def violations(self) -> list[Violation]:
        return self._violations

    def __bool__(self) -> bool:
        return self._value is not None

    def unwrap(self) -> V:
        return cast(V, self._value)


class Parser:
    """
    Parser scrubs through tokens given a file to extract relevant parts of
    the notebook.
    """

    @staticmethod
    def from_file(filename: Union[str, Path]) -> Parser:
        return Parser(contents=Path(filename).read_text(encoding="utf-8"))

    def __init__(self, contents: str):
        self.extractor = Extractor(contents=contents)

    def node_stack(self) -> PeekStack[Node]:
        return PeekStack(iter(ast.parse(self.extractor.contents or "").body))

    def parse_header(self, body: PeekStack[Node]) -> ParseResult[Header]:
        # header? = (docstring | comments)*
        while node := next(body):
            # Just string, comments are stripped
            if not is_string(node):
                break

        if not node:
            end_lineno = len(self.extractor.lines) - 1
            end_col_offset = len(self.extractor.lines[-1])
            return ParseResult(
                Header(
                    lineno=0,
                    col_offset=0,
                    end_lineno=end_lineno,
                    end_col_offset=end_col_offset,
                    value=self.extractor.extract_from_offsets(
                        0, 0, end_lineno, end_col_offset
                    ),
                )
            )

        return ParseResult(
            Header(
                lineno=0,
                col_offset=0,
                end_lineno=node.lineno - 1,
                end_col_offset=node.col_offset,
                value=self.extractor.extract_from_offsets(
                    0, 0, node.lineno - 1, node.col_offset
                ),
            )
        )

    def parse_import(self, body: PeekStack[Node]) -> ParseResult[Node]:
        # app = import marimo + __generated_with + App(kwargs*)
        violations: list[Violation] = []

        # Attempt to find import statement
        node = body.last
        while node:
            if is_marimo_import(node):
                return ParseResult(node, violations=violations)
            violations.append(
                Violation(
                    "Unexpected statement (expected marimo import)",
                    lineno=node.lineno,
                )
            )
            node = next(body)
        return ParseResult(violations=violations)

    def parse_version(self, body: PeekStack[Node]) -> ParseResult[str]:
        # __generated_with not being correctly set should not break marimo.
        violations: list[Violation] = []
        node = body.peek()
        version = _maybe_version(node) if node else None
        if not version:
            lineno = node.lineno if node else 0
            violations.append(
                Violation(
                    "Expected `__generated_with` assignment for marimo version number.",
                    lineno=lineno,
                )
            )
        else:
            # dequeue since version was consumed
            next(body)
        return ParseResult(version, violations=violations)

    def parse_app(
        self, body: PeekStack[Node]
    ) -> ParseResult[AppInstantiation]:
        # app = import marimo + __generated_with + App(kwargs*)
        violations: list[Violation] = []
        node = body.last
        while node:
            if is_app_def(node):
                # type caught by is_app_def
                _kwargs, _violations = _eval_kwargs(node.value.keywords)  # type: ignore
                violations.extend(_violations)
                return ParseResult(
                    AppInstantiation(
                        options=_kwargs,
                    )
                )
            violations.append(
                Violation(
                    "Unexpected statement, expected App initialization.",
                    node.lineno,
                )
            )
            node = next(body)

        return ParseResult(violations=violations)

    def parse_setup(self, body: PeekStack[Node]) -> ParseResult[SetupCell]:
        # setup? = Async?With(kwargs*, stmt*)
        violations: list[Violation] = []
        node = body.last
        maybe_setup = node
        while node:
            if is_cell(maybe_setup := body.peek()):
                break
            node = next(body)
            if not node:
                return ParseResult(violations=violations)
            violations.append(
                Violation(
                    "Unexpected statement, expected cell definitions.",
                    node.lineno,
                )
            )

        if maybe_setup and is_setup_cell(maybe_setup):
            next(body)
            return ParseResult(
                self.extractor.to_setup_cell(maybe_setup),
                violations=violations,
            )
        return ParseResult(violations=violations)

    def parse_body(self, body: PeekStack[Node]) -> ParseResult[list[CellDef]]:
        # Continue with remainder of body
        cells = []
        violations: list[Violation] = []

        while node := next(body):
            if is_body_cell(node):
                cells.append(self.extractor.to_cell(node))
            elif is_run_guard(node):
                break
            else:
                violations.append(
                    Violation(
                        "Unexpected statement, expected body cell definition.",
                        node.lineno,
                    )
                )
        return ParseResult(
            cells,
            violations=violations,
        )


class PeekStack(Generic[U]):
    """Builtins don't have a peek, which is useful here."""

    def __init__(self, iterable: Iterator[U]):
        self._iterable = iterable
        self._next: Optional[U] = None
        self.last: Optional[U] = None

    def __next__(self) -> Optional[U]:
        if self._next:
            self.last = self._next
            self._next = None
        else:
            try:
                self.last = next(self._iterable)
            except StopIteration:
                self.last = None
        return self.last

    def peek(self) -> Optional[U]:
        if self._next:
            return self._next
        try:
            self._next = next(self._iterable)
        except StopIteration:
            self._next = None
        return self._next


def _maybe_kwargs(
    node: Optional[ast.expr],
) -> tuple[dict[str, Any], list[Violation]]:
    if isinstance(node, ast.Call):
        return _eval_kwargs(node.keywords)
    elif node is None or isinstance(node, ast.Attribute):
        return {}, []
    raise MarimoFileError(f"Provided node ({node}) is not an attribute.")


def _maybe_version(node: Node) -> Optional[str]:
    # Expected ast:
    #
    #    Assign(
    #      targets=[
    #        Name(id='__generated_with', ctx=Store())],
    #      value=Constant(value=...)
    #    )
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__generated_with"
        and isinstance(node.value, ast.Constant)
    ):
        return str(node.value.value)
    return None


def _eval_kwargs(
    keywords: list[ast.keyword],
) -> tuple[dict[str, Any], list[Violation]]:
    """Convert a list of keyword arguments to a dictionary."""
    kwargs = {}
    violations = []
    for kw in keywords:
        # Only accept Constants
        if kw.arg and isinstance(kw.value, ast.Constant):
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


def _none_to_0(n: Optional[int]) -> int:
    return n if n is not None else 0


def extract_offsets_post_colon(
    function_code: str, block_start: str = "def"
) -> tuple[int, int]:
    # tokenize to find the start of the function body, including
    # comments --- we have to use tokenize because the ast treats the first
    # line of code as the starting line of the function body, whereas we
    # want the first indented line after the signature
    tokens = PeekStack(
        tokenize(io.BytesIO(function_code.encode("utf-8")).readline)
    )

    def_node: Optional[TokenInfo] = None
    while token := next(tokens):
        if token.type == token_types.NAME and token.string == block_start:
            def_node = token
            break
    assert def_node is not None

    paren_counter: Optional[int] = None
    token = tokens.peek()
    while token := next(tokens):
        if token.type == token_types.OP and token.string == "(":
            paren_counter = 1 if paren_counter is None else paren_counter + 1
        elif token.type == token_types.OP and token.string == ")":
            assert paren_counter is not None
            paren_counter -= 1

        # NB. Paren counter is initially _None_
        # So this doesn't activate until we see the first paren.
        if paren_counter == 0:
            break
        elif paren_counter is None:
            # In the setup block case, parens are not bound to be present.
            next_token = tokens.peek()
            if (
                next_token
                and next_token.type == token_types.OP
                and next_token.string == ":"
            ):
                paren_counter = 0
                break

    assert paren_counter == 0

    while token := next(tokens):
        if token.type == token_types.OP and token.string == ":":
            break

    after_colon = next(tokens)
    assert after_colon
    start_line: int
    start_col: int
    if after_colon.type == token_types.NEWLINE:
        fn_body_token = next(tokens)
        assert fn_body_token
        start_line = fn_body_token.start[0] - 1
        start_col = 0
    elif after_colon.type == token_types.COMMENT:
        newline_token = next(tokens)
        assert newline_token
        assert newline_token.type == token_types.NEWLINE
        fn_body_token = next(tokens)
        assert fn_body_token
        start_line = fn_body_token.start[0] - 1
        start_col = 0
    else:
        # function body starts on same line as definition, such as in
        # the following examples:
        #
        # def foo(): pass
        #
        # def foo(): x = 0; return x
        #
        # def foo(): x = """
        #
        # """; return x
        fn_body_token = after_colon
        start_line = fn_body_token.start[0] - 1
        start_col = fn_body_token.start[1]

    col_offset = fn_body_token.end[1] - start_col
    return start_line, col_offset


def is_equal_ast(
    basis: Optional[Union[ast.AST, list[ast.AST]]],
    other: Optional[Union[ast.AST, list[ast.AST]]],
) -> bool:
    """Compare two AST nodes for equality."""
    if type(basis) is not type(other):
        return False
    elif basis is None or other is None:
        return basis == other
    elif isinstance(basis, list):
        assert isinstance(other, list)
        if len(basis) != len(other):
            return False
        return all(is_equal_ast(a, b) for a, b in zip(basis, other))

    for key, value in vars(basis).items():
        # Scrub positional data not relevant for comparison.
        if key in {
            "lineno",
            "end_lineno",
            "col_offset",
            "end_col_offset",
            "ctx",
        }:
            continue
        other_value = getattr(other, key, None)
        if isinstance(value, (ast.AST, list, type(None))):
            return is_equal_ast(value, other_value)
        elif value != other_value:
            return False
    return True


def get_valid_decorator(
    node: CellNode,
) -> Optional[Union[ast.Attribute, ast.Call]]:
    valid_decorators = (
        "cell",
        "function",
        "class_definition",
    )
    for decorator in node.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and decorator.func.attr in valid_decorators  # type: ignore
        ) or (
            isinstance(decorator, ast.Attribute)
            and decorator.attr in valid_decorators
        ):
            return decorator
    return None


def is_marimo_import(node: Node) -> bool:
    return isinstance(node, ast.Import) and node.names[0].name == "marimo"


def is_string(node: Node) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def is_app_def(node: Node) -> bool:
    # Expected Ast:
    #
    #    Assign(
    #      targets=[
    #        Name(id='app', ctx=Store())],
    #      value=Call(
    #        func=Attribute(
    #          value=Name(id='marimo', ctx=Load()),
    #          attr='App',
    #          ctx=Load()),
    #        args=[],
    #        keywords=[
    #          keyword(
    #            arg=...,
    #            value=Constant(value=...)),
    #        ]
    #      )
    #    )

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


def is_cell_decorator(decorator: ast.expr) -> bool:
    if isinstance(decorator, ast.Attribute):
        return (
            isinstance(decorator.value, ast.Name)
            and decorator.value.id == "app"
            and decorator.attr in ("cell", "function", "class_definition")
        )
    elif isinstance(decorator, ast.Call):
        return is_cell_decorator(decorator.func)
    return False


def is_unparsable_cell(node: Node) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "app"
        and node.value.func.attr == "_unparsable_cell"
        and len(node.value.args) == 1
    )


def is_body_cell(node: Node) -> bool:
    # should have decorator @app.cell, @app.function, @app.class_definition
    return (
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and (decorator := get_valid_decorator(node))
        and is_cell_decorator(decorator)
    ) or is_unparsable_cell(node)


def _is_setup_call(node: Node) -> bool:
    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == "app"
            and node.attr == "setup"
        )
    elif isinstance(node, ast.Call):
        return _is_setup_call(node.func)
    return False


def is_setup_cell(node: Node) -> bool:
    return (
        isinstance(node, (ast.AsyncWith, ast.With))
        and len(node.items) == 1
        and _is_setup_call(node.items[0].context_expr)
    )


def is_cell(node: Optional[Node]) -> bool:
    return bool(node and (is_setup_cell(node) or is_body_cell(node)))


def is_run_guard(node: Optional[Node]) -> bool:
    basis = ast.parse('if __name__ == "__main__": app.run()').body[0]
    return bool(node and is_equal_ast(basis, node))


def parse_notebook(contents: str) -> Optional[NotebookSerialization]:
    parser = Parser(contents)
    if not parser.extractor.contents:
        return None

    violations: list[Violation] = []
    cells: list[CellDef] = []

    body: PeekStack[Node] = parser.node_stack()

    header_result = parser.parse_header(body)
    violations.extend(header_result.violations)
    header = header_result.unwrap()

    if not (import_result := parser.parse_import(body)):
        violations.append(
            Violation(
                "Only able to extract header.",
                lineno=1,
            )
        )
        return NotebookSerialization(
            header=Header(
                lineno=0,
                col_offset=0,
                end_lineno=len(parser.extractor.lines),
                end_col_offset=len(parser.extractor.lines[-1]),
                value=parser.extractor.contents,
            ),
            version=None,
            app=AppInstantiation(),
            cells=[],
            violations=violations,
            valid=False,
        )
    violations.extend(import_result.violations)

    version = None
    if version_result := parser.parse_version(body):
        version = version_result.unwrap()
    violations.extend(version_result.violations)

    if not (app_result := parser.parse_app(body)):
        raise MarimoFileError("`marimo.App` definition expected.")
    app = app_result.unwrap()
    violations.extend(app_result.violations)

    setup_result = parser.parse_setup(body)
    violations.extend(setup_result.violations)
    if setup_cell := setup_result.unwrap():
        cells.append(setup_cell)

    if is_run_guard(body.last):
        return NotebookSerialization(
            header=header,
            version=version,
            app=app,
            violations=violations,
            cells=cells,
        )

    body_result = parser.parse_body(body)
    cells.extend(body_result.unwrap())
    violations.extend(body_result.violations)

    # Expected a run guard, but that's OK.
    if not is_run_guard(body.last):
        violations.append(Violation("Expected run guard statement"))

    return NotebookSerialization(
        header=header,
        version=version,
        app=app,
        cells=cells,
        violations=violations,
    )
