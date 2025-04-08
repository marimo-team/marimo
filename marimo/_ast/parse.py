# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import ast
<<<<<<< HEAD
from typing import TYPE_CHECKING, Any, Optional

from textwrap import dedent

=======
import io
import token as token_types
from textwrap import dedent
from tokenize import TokenInfo, tokenize
from typing import TYPE_CHECKING, Any, Optional, Union

from marimo._ast.names import DEFAULT_CELL_NAME, SETUP_CELL_NAME
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    ClassCell,
    FunctionCell,
    Header,
    NotebookSerialization,
<<<<<<< HEAD
=======
    SetupCell,
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    UnparsableCell,
    Violation,
)

if TYPE_CHECKING:
<<<<<<< HEAD
    from collections.abc import Generator
=======
    from collections.abc import Generator, Iterator
    from typing_extensions import TypeAlias


FnNode: TypeAlias = Union[ast.FunctionDef, ast.AsyncFunctionDef]
CellNode: TypeAlias = Union[FnNode, ast.ClassDef]
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267


class MarimoFileError(Exception):
    pass


<<<<<<< HEAD
class _Extractor:
    def __init__(self, filename: Optional[str]):
        self.contents = None
        if filename is not None:
            with open(filename, encoding="utf-8") as f:
                self.contents = f.read().strip()
=======
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


def _0(n: Optional[int]) -> int:
    return n if n is not None else 0


class Extractor:
    def __init__(
        self, filename: Optional[str] = None, contents: Optional[str] = None
    ):
        self.contents = None
        if filename is not None:
            assert contents is None, (
                "Cannot provide both filename and contents"
            )
            with open(filename, encoding="utf-8") as f:
                self.contents = f.read().strip()
        elif contents is not None:
            self.contents = contents
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267

        self.lines = self.contents.splitlines() if self.contents else []

    def extract_from_offsets(
<<<<<<< HEAD
        self, lineno, col_offset, end_lineno, end_col_offset
=======
        self,
        lineno: int,
        col_offset: int,
        end_lineno: int,
        end_col_offset: Optional[int],
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    ) -> str:
        if lineno == end_lineno:
            return self.lines[lineno][col_offset:end_col_offset]
        if lineno + 1 == end_lineno:
<<<<<<< HEAD
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
=======
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

    def extract_from_code(self, node: ast.Node) -> str:
        if hasattr(node, "decorator_list"):
            if len(node.decorator_list):
                assert isinstance(
                    node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)
                )
                decorator = get_valid_decorator(node)  # type: ignore
                if not decorator:
                    lineno = node.lineno - 1
                    col_offset = node.col_offset
                else:
                    lineno = _0(decorator.end_lineno)
                    col_offset = decorator.col_offset - 1
            else:
                lineno = node.lineno - 1
                col_offset = node.col_offset
        else:
            lineno = node.lineno
            col_offset = node.col_offset

        code = self.extract_from_offsets(
            lineno,
            col_offset,
            _0(node.end_lineno) - 1,
            _0(node.end_col_offset),
        )
        return dedent(code)

    def to_cell_def(self, node: FnNode, kwargs: dict[str, Any]) -> CellDef:
        function_code = self.extract_from_code(node)
        lineno, col_offset = extract_offsets_post_colon(
            function_code,
            block_start="def",
        )

        end_lineno = _0(node.end_lineno)
        end_col_offset = node.end_col_offset
        if len(node.body) > 0:
            if node.lineno - node.body[0].lineno == 0:
                # python 3.9
                if not isinstance(
                    getattr(node.body[0], "value", None), ast.Ellipsis
                ):
                    col_offset += node.body[0].col_offset - 1
                else:
                    col_offset += node.body[0].col_offset - 3
            else:
                col_offset = 0

            has_return = isinstance(node.body[-1], ast.Return)
            if has_return:
                # we need to adjust for the trailing return statement
                # which is not included in the function body
                if len(node.body) > 1:
                    end_lineno = max(
                        _0(node.body[-2].end_lineno), node.body[-1].lineno - 1
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
                    if node.lineno + lineno - node.body[0].lineno == 0:
                        return CellDef(
                            code="",
                            options=kwargs,
                            lineno=node.lineno + lineno,
                            col_offset=node.col_offset + col_offset,
                            end_lineno=node.lineno + lineno,
                            end_col_offset=len(self.lines[-1]),
                            name=getattr(node, "name", DEFAULT_CELL_NAME),
                        )
                    else:
                        end_lineno = node.body[-1].lineno - 1
                        end_col_offset = None
        cell_code = self.extract_from_offsets(
            lineno=node.lineno + lineno - 1,
            col_offset=col_offset,
            end_lineno=end_lineno - 1,
            end_col_offset=end_col_offset,
        )

        # TODO: Feels pretty hacky, would love if someone had a suggestion for this
        # But the only other better way (I can see) is to drop down to the
        # toeknizer lever and handle it there + handle particular edge
        # cases.
        #
        # If the last value is not a return statement, we need to grab
        # trailing comments.
        if not has_return:
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
            cell_code += "\n".join(
                self.lines[end_lineno : new_end + 1]
            ).rstrip()
            end_lineno = new_end - 1

        if end_col_offset is None:
            end_col_offset = 0
        return CellDef(
            code=dedent(cell_code),
            options=kwargs,
            lineno=node.lineno + lineno,
            col_offset=node.col_offset + col_offset,
            end_lineno=_0(node.end_lineno) + end_lineno,
            end_col_offset=_0(node.end_col_offset) + end_col_offset,
            name=getattr(node, "name", DEFAULT_CELL_NAME),
        )

    def to_cell(
        self, node: ast.stmt, attribute: Optional[str] = None
    ) -> CellDef:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        """Convert an AST node to a CellDef."""
        if isinstance(
            node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
<<<<<<< HEAD
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
=======
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
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
                    code=self.extract_from_code(node),
                    _ast=node,
                    options=kwargs,
                )

<<<<<<< HEAD
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
=======
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
        elif is_setup_cell(node):
            kwargs, _violations = _maybe_kwargs(node.items[0].context_expr)  # type: ignore
            code = self.extract_from_code(node)
            return SetupCell(
                code=dedent(code),
                options=kwargs,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=max(node.lineno, _0(node.end_lineno)),
                end_col_offset=_0(node.end_col_offset),
                name=SETUP_CELL_NAME,
            )

        raise MarimoFileError(
            "Unexpected node type for cell extraction. "
            "Please report this issue to the Marimo team with "
            "your code if possible: "
            "github.com/marimo-team/marimo/issues"
        )


def extract_offsets_post_colon(
    function_code: str, block_start: str = "def"
) -> (int, int):
    # tokenize to find the start of the function body, including
    # comments --- we have to use tokenize because the ast treats the first
    # line of code as the starting line of the function body, whereas we
    # want the first indented line after the signature
    tokens: Generator[TokenInfo] = _peek_stack(
        tokenize(io.BytesIO(function_code.encode("utf-8")).readline)
    )

    def_node: Optional[TokenInfo] = None
    while token := next(tokens):
        if token.type == token_types.NAME and token.string == block_start:
            def_node = token
            break
    assert def_node is not None

    paren_counter: Optional[int] = None
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
            if token.type == token_types.OP and token.string == ":":
                # Put the colon back on the stack
                tokens.send(token)
                paren_counter = 0
                break

    assert paren_counter == 0

    while token := next(tokens):
        if token.type == token_types.OP and token.string == ":":
            break

    after_colon = next(tokens)
    start_line: int
    start_col: int
    if after_colon.type == token_types.NEWLINE:
        fn_body_token = next(tokens)
        start_line = fn_body_token.start[0] - 1
        start_col = 0
    elif after_colon.type == token_types.COMMENT:
        newline_token = next(tokens)
        assert newline_token.type == token_types.NEWLINE
        fn_body_token = next(tokens)
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


def _maybe_kwargs(
    node: Optional[ast.expr],
) -> tuple[dict[str, Any], list[Violation]]:
    if isinstance(node, ast.Call):
        return _eval_kwargs(node.keywords)
    elif node is None or isinstance(node, ast.Attribute):
        return {}, []
    raise MarimoFileError(f"Provided node ({node}) is not an attribute.")


def _maybe_version(node: ast.expr) -> Optional[str]:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    # Assign(
    #   targets=[
    #     Name(id='__generated_with', ctx=Store())],
    #   value=Constant(value=...)
    # )
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        if isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "__generated_with":
                if isinstance(node.value, ast.Constant):
<<<<<<< HEAD
                    return node.value.value


def _gen_stack(iterable) -> Generator[ast.stmt, ast.stmt, None]:
    """A generator that yields items from the iterable."""
    for item in iterable:
        value = yield item
        if value is not None:
            yield value
    while True:
        yield None
=======
                    return str(node.value.value)


def _peek_stack(iterable) -> Generator[ast.expr, ast.expr, None]:
    """
    Wrapper to make a "peekable" generator.
    To restack a value, use "send" to yield it back to the generator.
    """
    for item in iterable:
        value = yield item
        if value is not None:
            for peeked in [value, item]:
                response = yield peeked
                if response is not None:
                    raise ValueError("Cannot restack consecutive items")
    while True:
        value = yield None
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        if value is not None:
            yield value


<<<<<<< HEAD
def _eval_kwargs(keywords: list[ast.keyword]) -> dict[str, Any]:
=======
def _eval_kwargs(
    keywords: list[ast.keyword],
) -> tuple[dict[str, Any], list[Violation]]:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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


<<<<<<< HEAD
def is_marimo_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.Import) and node.names[0].name == "marimo"


def is_string(node: ast.stmt) -> bool:
=======
def is_marimo_import(node: ast.expr) -> bool:
    return isinstance(node, ast.Import) and node.names[0].name == "marimo"


def is_string(node: ast.expr) -> bool:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


<<<<<<< HEAD
def is_app_def(node: ast.stmt) -> bool:
=======
def is_app_def(node: ast.expr) -> bool:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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


<<<<<<< HEAD
def is_cell_decorator(decorator: ast.stmt) -> bool:
=======
def is_cell_decorator(decorator: ast.expr) -> bool:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    if isinstance(decorator, ast.Attribute):
        return (
            isinstance(decorator.value, ast.Name)
            and decorator.value.id == "app"
            and decorator.attr in ("cell", "function", "class_definition")
        )
    elif isinstance(decorator, ast.Call):
        return is_cell_decorator(decorator.func)
    return False


<<<<<<< HEAD
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
=======
def is_unparsable_cell(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "app"
        and node.value.func.attr == "_unparsable_cell"
        and len(node.value.args) == 1
    )


def is_body_cell(node: ast.expr) -> bool:
    # should have decorator @app.cell, @app.function, @app.class_definition
    return (
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and (decorator := get_valid_decorator(node))
        and is_cell_decorator(decorator)
    ) or is_unparsable_cell(node)


def _is_setup_call(node: ast.expr) -> bool:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == "app"
            and node.attr == "setup"
        )
    elif isinstance(node, ast.Call):
        return _is_setup_call(node.func)
    return False


<<<<<<< HEAD
def is_setup_cell(node: ast.stmt) -> bool:
=======
def is_setup_cell(node: ast.expr) -> bool:
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
    return (
        isinstance(node, (ast.AsyncWith, ast.With))
        and len(node.items) == 1
        and _is_setup_call(node.items[0].context_expr)
    )


<<<<<<< HEAD
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
=======
def is_cell(node: ast.expr) -> bool:
    return is_setup_cell(node) or is_body_cell(node)


def is_run_guard(node: ast.expr) -> bool:
    return node == ast.parse('if __name__ == "__main__": app.run()').body[0]


def parse_notebook(filename: str) -> NotebookSerialization:
    extractor = Extractor(filename)
    if not extractor.contents:
        return None

    body = _peek_stack(ast.parse(extractor.contents).body)
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267

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
<<<<<<< HEAD
        # TODO(dmadisetti): Raise an error or add severity to violations?
        raise MarimoFileError("File only contains a header.")
=======
        violations.append(
            Violation(
                "File only contains a header.",
                lineno=1,
            )
        )
        return NotebookSerialization(
            header=Header(
                lineno=0,
                col_offset=0,
                end_lineno=len(extractor.lines),
                end_col_offset=len(extractor.lines[-1]),
                value=extractor.contents,
            ),
            version=None,
            app=AppInstantiation(),
            cells=[],
            violations=violations,
            valid=False,
        )
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267

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
<<<<<<< HEAD
=======
        # TODO(dmadisetti): Raise an error or add severity to violations?
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        raise MarimoFileError("`marimo` import expected.")

    # __generated_with not being correctly set should not break marimo.
    node = next(body)
    version = _maybe_version(node)
    if not version:
        # Put whatever this was, back on the stack
        body.send(node)

        violations.append(
            Violation(
<<<<<<< HEAD
                "Expected `__generated_with` assigment for marimo version number.",
=======
                "Expected `__generated_with` assignment for marimo version number.",
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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
