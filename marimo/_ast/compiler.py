# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import io
import linecache
import os
import re
import textwrap
import token as token_types
from tokenize import TokenInfo, tokenize
from typing import TYPE_CHECKING, Any, Callable, Optional

from marimo import _loggers
from marimo._ast.cell import (
    Cell,
    CellImpl,
    ImportWorkspace,
    SourcePosition,
)
from marimo._ast.variables import is_local
from marimo._ast.visitor import ImportData, Name, ScopedVisitor
from marimo._types.ids import CellId_t
from marimo._utils.tmpdir import get_tmpdir

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Iterator


def code_key(code: str) -> int:
    return hash(code)


def cell_id_from_filename(filename: str) -> Optional[CellId_t]:
    """Parse cell id from filename."""
    matches = re.findall(r"__marimo__cell_(.*?)_", filename)
    if matches:
        return CellId_t(matches[0])
    return None


def get_filename(cell_id: CellId_t, suffix: str = "") -> str:
    """Get a temporary Python filename that encodes the cell id in it."""
    basename = f"__marimo__cell_{cell_id}_"
    return os.path.join(get_tmpdir(), basename + suffix + ".py")


def ends_with_semicolon(code: str) -> bool:
    """Returns True if the cell's code ends with a semicolon, ignoring whitespace and comments.

    Args:
        code: The cell's source code
    Returns:
        bool: True if the last non-comment line ends with a semicolon
    """
    # Tokenize to check for semicolon
    tokens = tokenize(io.BytesIO(code.strip().encode("utf-8")).readline)
    for token in reversed(list(tokens)):
        if token.type in (
            token_types.ENDMARKER,
            token_types.NEWLINE,
            token_types.NL,
            token_types.COMMENT,
        ):
            continue
        return token.string == ";"
    return False


def contains_only_tests(tree: ast.Module) -> bool:
    """Returns True if the module contains only test functions."""
    scope = tree.body
    for node in scope:
        if isinstance(node, ast.Return):
            return True
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            return False
        if not node.name.lower().startswith("test"):
            return False
    return bool(scope)


def cache(filename: str, code: str) -> None:
    # Generate a cache entry in Python's linecache
    linecache.cache[filename] = (
        len(code),
        None,
        [line + "\n" for line in code.splitlines()],
        filename,
    )


def fix_source_position(node: Any, source_position: SourcePosition) -> Any:
    # NOTE: This function closely mirrors python's native ast.increment_lineno
    # however, utilized here to also increment the col_offset of the node.
    # See https://docs.python.org/3/library/ast.html#ast.increment_lineno
    # for reference.
    line_offset = source_position.lineno
    col_offset = source_position.col_offset
    for child in ast.walk(node):
        # TypeIgnore is a special case where lineno is not an attribute
        # but rather a field of the node itself.
        # Note, TypeIgnore does not have a "col_offset"
        if isinstance(child, ast.TypeIgnore):
            child.lineno = getattr(child, "lineno", 0) + line_offset
            continue

        if "lineno" in child._attributes:
            child.lineno = getattr(child, "lineno", 0) + line_offset

        if "col_offset" in child._attributes:
            child.col_offset = getattr(child, "col_offset", 0) + col_offset

        if (
            "end_lineno" in child._attributes
            and (end_lineno := getattr(child, "end_lineno", 0)) is not None
        ):
            child.end_lineno = end_lineno + line_offset

        if (
            "end_col_offset" in child._attributes
            and (end_col_offset := getattr(child, "end_col_offset", 0))
            is not None
        ):
            child.end_col_offset = end_col_offset + col_offset
    return node


def compile_cell(
    code: str,
    cell_id: CellId_t,
    source_position: Optional[SourcePosition] = None,
    carried_imports: list[ImportData] | None = None,
    test_rewrite: bool = False,
) -> CellImpl:
    # Replace non-breaking spaces with regular spaces -- some frontends
    # send nbsp in place of space, which is a syntax error.
    #
    # See https://github.com/pyodide/pyodide/issues/3337,
    #     https://github.com/marimo-team/marimo/issues/1546
    code = code.replace("\u00a0", " ")
    module = compile(
        code,
        "<unknown>",
        mode="exec",
        # don't inherit compiler flags, in particular future annotations
        dont_inherit=True,
        flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
    )
    if not module.body:
        # either empty code or just comments
        return CellImpl(
            key=hash(""),
            code=code,
            mod=module,
            defs=set(),
            refs=set(),
            temporaries=set(),
            variable_data={},
            deleted_refs=set(),
            language="python",
            body=None,
            last_expr=None,
            cell_id=cell_id,
        )

    is_test = contains_only_tests(module)
    is_import_block = all(
        isinstance(stmt, (ast.Import, ast.ImportFrom)) for stmt in module.body
    )

    v = ScopedVisitor("cell_" + cell_id)
    v.visit(module)

    expr: ast.Expression
    final_expr = module.body[-1]
    # Use final expression if it exists doesn't end in a
    # semicolon. Evaluates expression to "None" otherwise.
    if isinstance(final_expr, ast.Expr) and not ends_with_semicolon(code):
        expr = ast.Expression(module.body.pop().value)
        expr.lineno = final_expr.lineno
    else:
        const = ast.Constant(value=None)
        const.col_offset = final_expr.end_col_offset
        const.end_col_offset = final_expr.end_col_offset
        expr = ast.Expression(const)
        # use code over body since lineno corresponds to source
        const.lineno = len(code.splitlines()) + 1
        expr.lineno = const.lineno
    # Creating an expression clears source info, so it needs to be set back
    expr.col_offset = final_expr.end_col_offset
    expr.end_col_offset = final_expr.end_col_offset

    filename: str
    if source_position:
        # Modify the "source" position for meaningful stacktraces
        fix_source_position(module, source_position)
        fix_source_position(expr, source_position)
        filename = source_position.filename
    else:
        # store the cell's code in Python's linecache so debuggers can find it
        filename = get_filename(cell_id)
        # cache the entire cell's code, doesn't need to be done in source case
        # since there is an actual file to read from.
        cache(filename, code)

    # pytest assertion rewriting, gives more context for assertion failures.
    if is_test or test_rewrite:
        # pytest is not required, so fail gracefully if needed
        try:
            from _pytest.assertion.rewrite import (  # type: ignore
                rewrite_asserts,
            )

            rewrite_asserts(module, code.encode("utf-8"), module_path=filename)
        # general catch-all, in case of internal pytest API changes
        except Exception:
            LOGGER.warning(
                "pytest is not installed, skipping assertion rewriting"
            )

    flags = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    body = compile(
        module, filename, mode="exec", dont_inherit=True, flags=flags
    )
    last_expr = compile(
        expr, filename, mode="eval", dont_inherit=True, flags=flags
    )

    nonlocals = {name for name in v.defs if not is_local(name)}
    temporaries = v.defs - nonlocals
    variable_data = {
        name: v.variable_data[name]
        for name in nonlocals
        if name in v.variable_data
    }

    # If this cell is an import cell, we carry over any imports in
    # `carried_imports` that are also in this cell to the import workspace's
    # definitions.
    imported_defs: set[Name] = set()
    if is_import_block and carried_imports is not None:
        for data in variable_data.values():
            for datum in data:
                import_data = datum.import_data
                if import_data is None:
                    continue
                for previous_import_data in carried_imports:
                    if previous_import_data == import_data:
                        imported_defs.add(import_data.definition)

    return CellImpl(
        # keyed by original (user) code, for cache lookups
        key=code_key(code),
        code=code,
        mod=module,
        defs=nonlocals,
        refs=v.refs,
        temporaries=temporaries,
        variable_data=variable_data,
        import_workspace=ImportWorkspace(
            is_import_block=is_import_block,
            imported_defs=imported_defs,
        ),
        deleted_refs=v.deleted_refs,
        language=v.language,
        body=body,
        last_expr=last_expr,
        cell_id=cell_id,
        _test=is_test,
    )


def get_source_position(
    f: Callable[..., Any], lineno: int, col_offset: int
) -> Optional[SourcePosition]:
    # Fallback won't capture embedded scripts
    is_script = f.__globals__["__name__"] == "__main__"
    # TODO: spec is None for markdown notebooks, which is fine for now
    if module := inspect.getmodule(f):
        spec = module.__spec__
        is_script = spec is None or spec.name != "marimo_app"

    if not is_script:
        return None

    return SourcePosition(
        filename=f.__code__.co_filename,
        lineno=lineno,
        col_offset=col_offset,
    )


def toplevel_cell_factory(
    f: Callable[..., Any],
    cell_id: CellId_t,
    anonymous_file: bool = False,
    test_rewrite: bool = False,
) -> Cell:
    """Creates a cell containing a function.

    NB: Unlike cell_factory, this utilizes the function itself as the cell
    definition. As such, signature and return type are important.
    """
    code, lnum = inspect.getsourcelines(f)
    function_code = textwrap.dedent("".join(code))

    # We need to scrub through the initial decorator. Since we don't care about
    # indentation etc, easiest just to use AST.

    tree = ast.parse(function_code, type_comments=True)
    try:
        decorator = tree.body[0].decorator_list.pop(0)  # type: ignore
        # NB. We don't unparse from the AST because it strips comments.
        cell_code = textwrap.dedent(
            "".join(code[decorator.end_lineno :])
        ).strip()
    except (IndexError, AttributeError) as e:
        raise ValueError(
            "Unexpected usage (expected decorated function)"
        ) from e

    source_position = None
    if not anonymous_file:
        source_position = get_source_position(
            f,
            lnum + decorator.end_lineno - 1,  # Scrub the decorator
            0,
        )

    cell = compile_cell(
        cell_code,
        cell_id=cell_id,
        source_position=source_position,
        test_rewrite=test_rewrite,
    )
    return Cell(
        _name=f.__name__,
        _cell=cell,
        _test_allowed=cell._test or f.__name__.startswith("test_"),
    )


def cell_factory(
    f: Callable[..., Any],
    cell_id: CellId_t,
    anonymous_file: bool = False,
    test_rewrite: bool = False,
) -> Cell:
    """Creates a cell from a function.

    The signature and returns of the function are not used
    to generate refs and defs. If the user introduced errors to the
    signature, marimo will autofix them on save.
    """
    code, lnum = inspect.getsourcelines(f)
    function_code = textwrap.dedent("".join(code))

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

    col_offset = fn_body_token.end[1] - start_col

    # it would be difficult to tell if the last return token were in fact the
    # last statement of the function body, so we use the ast, which lets us
    # easily find the last statement of the function body;
    tree = ast.parse(function_code)
    return_node: Optional[ast.Return]
    first_stmt = tree.body[0]
    # Handle case where first statement does not have a body
    if not hasattr(first_stmt, "body"):
        return_node = None
    else:
        return_node = (
            first_stmt.body[-1]  # type: ignore
            if isinstance(first_stmt.body[-1], ast.Return)  # type: ignore
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

    # anonymous file is required for deterministic testing.
    source_position = None
    if not anonymous_file:
        source_position = get_source_position(
            f, lnum + start_line - 1, col_offset
        )

    cell = compile_cell(
        cell_code,
        cell_id=cell_id,
        source_position=source_position,
        test_rewrite=test_rewrite,
    )
    return Cell(
        _name=f.__name__,
        _cell=cell,
        _test_allowed=cell._test or f.__name__.startswith("test_"),
    )
