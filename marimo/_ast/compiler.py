# Copyright 2024 Marimo. All rights reserved.
import ast
import inspect
import io
import linecache
import os
import sys
import textwrap
import token as token_types
from collections.abc import Iterator
from tokenize import TokenInfo, tokenize
from typing import Optional, Set, Union, cast

from marimo._ast.cell import (
    Cell,
    CellFunction,
    CellFuncTypeBound,
    CellId_t,
    cell_function,
)
from marimo._ast.visitor import ScopedVisitor, _is_local
from marimo._utils.tmpdir import get_tmpdir


def code_key(code: str) -> int:
    return hash(code)


def get_filename(basename: str) -> str:
    """Get a temporary Python filename that ends with basename."""
    return os.path.join(get_tmpdir(), basename + ".py")


def cache(filename: str, code: str) -> None:
    # Generate a cache entry in Python's linecache
    linecache.cache[filename] = (
        len(code),
        None,
        [line + "\n" for line in code.splitlines()],
        filename,
    )


def compile_cell(
    code: str,
    cell_id: CellId_t,
    basename: Optional[str] = None,
) -> Cell:
    module = ast.parse(code, mode="exec")
    if not module.body:
        # either empty code or just comments
        return Cell(
            key=hash(""),
            code=code,
            mod=module,
            defs=set(),
            refs=set(),
            deleted_refs=set(),
            body=None,
            last_expr=None,
            cell_id=cell_id,
        )

    v = ScopedVisitor("cell_" + str(cell_id) if cell_id is not None else None)
    v.visit(module)

    expr: Union[ast.Expression, str]
    if isinstance(module.body[-1], ast.Expr):
        expr = ast.Expression(module.body.pop().value)  # type: ignore
    else:
        expr = "None"

    # store the cell's code in Python's linecache so debuggers can find it
    basename = f"cell_{cell_id}" if basename is None else basename
    body_filename = get_filename(basename)
    last_expr_filename = get_filename(basename + "_output")
    cache(body_filename, code)
    if sys.version_info >= (3, 9):
        # ast.unparse only available >= 3.9
        cache(
            last_expr_filename,
            ast.unparse(expr) if not isinstance(expr, str) else "None",
        )

    body = compile(module, body_filename, mode="exec")
    last_expr = compile(expr, last_expr_filename, mode="eval")

    glbls = {name for name in v.defs if not _is_local(name)}
    return Cell(
        # keyed by original (user) code, for cache lookups
        key=code_key(code),
        code=code,
        mod=module,
        defs=glbls,
        refs=v.refs,
        deleted_refs=v.deleted_refs,
        body=body,
        last_expr=last_expr,
        cell_id=cell_id,
    )


def cell_factory(
    f: CellFuncTypeBound,
    cell_id: CellId_t,
) -> CellFunction[CellFuncTypeBound]:
    """Creates a cell from a function.

    The signature and returns of the function are not used
    to generate refs and defs. If the user introduced errors to the
    signature, marimo will autofix them on save.
    """
    function_code = textwrap.dedent(inspect.getsource(f))

    # tokenize to find the start of the function body, including
    # comments --- we have to use tokenize because the ast treats the first
    # line of code as the starting line of the function body, whereas we
    # want the first indented line after the signature
    tokens: Iterator[TokenInfo] = tokenize(
        io.BytesIO(function_code.encode("utf-8")).readline
    )

    def_node: Optional[TokenInfo] = None
    for token in tokens:
        if token.type == token_types.NAME and token.string == "def":
            def_node = token
            break
    assert def_node is not None

    paren_counter: Optional[int] = None
    for token in tokens:
        if token.type == token_types.OP and token.string == "(":
            paren_counter = 1 if paren_counter is None else paren_counter + 1
        elif token.type == token_types.OP and token.string == ")":
            assert paren_counter is not None
            paren_counter -= 1

        if paren_counter == 0:
            break
    assert paren_counter == 0

    for token in tokens:
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

    # it would be difficult to tell if the last return token were in fact the
    # last statement of the function body, so we use the ast, which lets us
    # easily find the last statement of the function body;
    tree = ast.parse(function_code)
    return_node = (
        tree.body[0].body[-1]  # type: ignore
        if isinstance(tree.body[0].body[-1], ast.Return)  # type: ignore
        else None
    )

    end_line, return_offset = (
        (return_node.lineno - 1, return_node.col_offset)
        if return_node is not None
        else (None, None)
    )

    cell_code: str
    lines = function_code.split("\n")
    if start_line == end_line:
        # remove leading indentation
        cell_code = textwrap.dedent(lines[start_line][start_col:return_offset])
    else:
        first_line = lines[start_line][start_col:]
        cell_code = textwrap.dedent(
            "\n".join([first_line] + lines[start_line + 1 : end_line])
        ).strip()
        if end_line is not None and not lines[end_line].strip().startswith(
            "return"
        ):
            # handle return written on same line as last statement in cell
            cell_code += "\n" + lines[end_line][:return_offset]

    arg_names = set(p.arg for p in tree.body[0].args.args)  # type: ignore
    # TODO(akshayka): use the name of the function as the basename (if not __)
    # for parse_cell
    ret = cell_function(
        compile_cell(cell_code, cell_id=cell_id),
        cast(Set[str], arg_names),
        function_code,
        f,
    )
    return ret
