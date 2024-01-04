# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import ast
import dataclasses
import functools
import inspect
import io
import textwrap
import token as token_types
from collections.abc import Iterator
from tokenize import TokenInfo, tokenize
from types import CodeType
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from marimo._ast.visitor import Name, ScopedVisitor, _is_local
from marimo._utils.deep_merge import deep_merge

CellId_t = str


def code_key(code: str) -> int:
    return hash(code)


@dataclasses.dataclass
class CellConfig:
    # If True, the cell and its descendants cannot be executed,
    # but they can still be added to the graph.
    disabled: bool = False

    # If True, the cell is hidden from the editor.
    hide_code: bool = False

    @classmethod
    def from_dict(cls, kwargs: dict[str, Any]) -> CellConfig:
        return cls(**{k: v for k, v in kwargs.items() if k in CellConfigKeys})

    def configure(self, update: dict[str, Any] | CellConfig) -> None:
        """Update the config in-place.

        `update` can be a partial config or a CellConfig
        """
        if isinstance(update, CellConfig):
            update = dataclasses.asdict(update)
        new_config = dataclasses.asdict(
            CellConfig.from_dict(deep_merge(dataclasses.asdict(self), update))
        )
        for key, value in new_config.items():
            self.__setattr__(key, value)


CellConfigKeys = frozenset(
    {field.name for field in dataclasses.fields(CellConfig)}
)

"""
idle: cell has run with latest inputs
queued: cell is queued to run
running: cell is running
stale: cell hasn't run with latest inputs, and can't run (disabled)
disabled-transitively: cell is disabled because a parent is disabled
"""
CellStatusType = Literal[
    "idle", "queued", "running", "stale", "disabled-transitively"
]


@dataclasses.dataclass
class CellStatus:
    state: Optional[CellStatusType] = None


@dataclasses.dataclass(frozen=True)
class Cell:
    # hash of code
    key: int
    code: str
    mod: ast.Module
    defs: set[Name]
    refs: set[Name]
    deleted_refs: set[Name]
    body: Optional[CodeType]
    last_expr: Optional[CodeType]
    # unique id
    cell_id: Optional[CellId_t]

    # Mutable fields
    # config: explicit configuration of cell
    config: CellConfig = dataclasses.field(default_factory=CellConfig)
    # staus: status, inferred at runtime
    _status: CellStatus = dataclasses.field(default_factory=CellStatus)

    def configure(self, update: dict[str, Any] | CellConfig) -> Cell:
        """Update the cel config.

        `update` can be a partial config.
        """
        self.config.configure(update)
        return self

    @property
    def status(self) -> Optional[CellStatusType]:
        return self._status.state

    @property
    def stale(self) -> bool:
        return self.status == "stale"

    @property
    def disabled_transitively(self) -> bool:
        return self.status == "disabled-transitively"

    def set_status(self, status: CellStatusType) -> None:
        from marimo._messaging.ops import CellOp
        from marimo._runtime.context import (
            ContextNotInitializedError,
            get_context,
        )

        self._status.state = status
        try:
            get_context()
        except ContextNotInitializedError:
            return

        assert self.cell_id is not None
        CellOp.broadcast_status(cell_id=self.cell_id, status=status)


CellFuncType = Callable[..., Optional[Tuple[Any, ...]]]
# Cumbersome, but used to ensure function types don't get erased in decorators
# or creation of CellFunction
CellFuncTypeBound = TypeVar(
    "CellFuncTypeBound",
    bound=Callable[..., Optional[Tuple[Any, ...]]],
)


class CellFunction(Protocol[CellFuncTypeBound]):
    """Wraps a function from which a Cell object was created."""

    cell: Cell
    # function name
    __name__: str
    # function code
    code: str
    # arg names of wrapped function
    args: set[str]
    __call__: CellFuncTypeBound


def cell_function(
    cell: Cell, args: set[str], code: str, f: CellFuncTypeBound
) -> CellFunction[CellFuncTypeBound]:
    signature = inspect.signature(f)

    n_args = 0
    defaults = {}
    for name, value in signature.parameters.items():
        if value.default != inspect.Parameter.empty:
            defaults[name] = value.default
        else:
            n_args += 1

    parameters = list(signature.parameters.keys())
    return_names = sorted(cell.defs)

    @functools.wraps(f)
    def func(*args: Any, **kwargs: Any) -> tuple[Any, ...]:
        """Wrapper for executing cell using the function's signature.

        Alternative for passing a globals dict
        """
        glbls = {}
        glbls.update(defaults)
        pos = 0
        for arg in args:
            glbls[parameters[pos]] = arg
            pos += 1
        if pos < n_args:
            raise TypeError(
                f.__name__
                + f"() missing {n_args - pos} required arguments: "
                + " and ".join(f"'{p}'" for p in parameters[pos:n_args])
            )

        for kwarg, value in kwargs.items():
            if kwarg not in parameters:
                raise TypeError(
                    f.__name__
                    + "() got an unexpected keyword argument '{kwarg}'"
                )
            else:
                glbls[kwarg] = value

        # we use execute_cell instead of calling `f` directly because
        # we want to obtain the cell's HTML output, which is the last
        # expression in the cell body.
        #
        # TODO: stash output if mo.collect_outputs() context manager is active
        #       ... or just make cell execution return the output in addition
        #       to the defs, which might be weird because that doesn't
        #       match the function signature
        _ = execute_cell(cell, glbls)
        return tuple(glbls[name] for name in return_names)

    cell_func = cast(CellFunction[CellFuncTypeBound], func)
    cell_func.cell = cell
    cell_func.args = args
    cell_func.code = code
    return cell_func


def parse_cell(
    code: str, filename: str = "<string>", cell_id: Optional[CellId_t] = None
) -> Cell:
    mod = ast.parse(code, mode="exec")
    if not mod.body:
        # either empty code or just comments
        return Cell(
            key=hash(""),
            code=code,
            mod=mod,
            defs=set(),
            refs=set(),
            deleted_refs=set(),
            body=None,
            last_expr=None,
            cell_id=cell_id,
        )

    v = ScopedVisitor("cell_" + str(cell_id) if cell_id is not None else None)
    v.visit(mod)

    expr: Union[ast.Expression, str]
    if isinstance(mod.body[-1], ast.Expr):
        expr = ast.Expression(mod.body.pop().value)  # type: ignore
    else:
        expr = "None"
    last_expr = compile(expr, filename, mode="eval")
    body = compile(mod, filename, mode="exec")

    glbls = {name for name in v.defs if not _is_local(name)}
    return Cell(
        # keyed by original (user) code, for cache lookups
        key=code_key(code),
        code=code,
        mod=mod,
        defs=glbls,
        refs=v.refs,
        deleted_refs=v.deleted_refs,
        body=body,
        last_expr=last_expr,
        cell_id=cell_id,
    )


def is_ws(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"


def cell_factory(f: CellFuncTypeBound) -> CellFunction[CellFuncTypeBound]:
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
    ret = cell_function(
        parse_cell(cell_code), cast(Set[str], arg_names), function_code, f
    )
    return ret


def execute_cell(cell: Cell, glbls: dict[Any, Any]) -> Any:
    if cell.body is None:
        return None
    assert cell.last_expr is not None
    exec(cell.body, glbls)
    return eval(cell.last_expr, glbls)
