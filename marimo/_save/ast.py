# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable, Sequence, cast

from marimo._utils.variables import unmangle_local

ARG_PREFIX: str = "*"


class BlockException(Exception):
    pass


def compiled_ast(block: Sequence[ast.AST | ast.stmt]) -> ast.Module:
    return cast(
        ast.Module,
        compile(
            ast.Module(block, type_ignores=[]),
            # <ast> is non-standard as a filename, but easier to debug than
            # <module> everywhere.
            "<ast>",
            mode="exec",
            flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            optimize=0,
            dont_inherit=True,
        ),
    )


def clean_to_modules(
    pre_block: list[ast.AST], block: ast.With
) -> tuple[ast.Module, ast.Module]:
    """Standardizes a `with` block to modules.

    Consider

    >>> <pre_block>
    >>> ...
    >>> </pre_block>
    >>> with fn(val:=other) as x:
    >>>   <block>
    >>>   ...
    >>>   </block>

    We want to compile <pre_block>, and <block> into two separate modules,
    however, line 4 removes the context of "x" and "val", so this is adjusted
    to:

    >>> <pre_block>
    >>> ...
    >>> x = fn(val := other)
    >>> </pre_block>
    >>> <block>
    >>> ...
    >>> </block>
    """
    assert len(block.items) == 1, "Unexpected with block structure."
    (with_block,) = block.items
    initializer: ast.AST = with_block.context_expr
    if with_block.optional_vars:
        initializer = ast.Assign(
            targets=[with_block.optional_vars],
            value=initializer,
        )
    else:
        # Edgecase with no "as" clause.
        initializer = ast.Expr(value=initializer)
    initializer.lineno = len(pre_block) + 1
    initializer.col_offset = 0
    pre_block.append(initializer)
    return (compiled_ast(pre_block), compiled_ast(block.body))


class ExtractWithBlock(ast.NodeTransformer):
    def __init__(self, line: int, *arg: Any, **kwargs: Any) -> None:
        super().__init__(*arg, **kwargs)
        self.target_line = line

    def generic_visit(self, node: ast.AST) -> tuple[ast.Module, ast.Module]:  #  type: ignore[override]
        pre_block = []

        # There are a few strange edges cases like:
        # >>> with open("file.txt"): pass
        #
        # It's difficult to properly delineate the block, so if multiple
        # things map to the same line number, it's best to throw an error.
        on_line = []
        previous = None

        assert isinstance(node, list), "Unexpected block structure."
        for n in node:
            # There's a chance that the block is first evaluated somewhere in a
            # multiline line expression, for instance:
            # 1 >>> with cache as c:
            # 2 >>>    a = [
            # 3 >>>        f(x) # <<< first frame call is here, and not line 2
            # 4 >>>    ]
            # so check that the "target" line is in the interval
            # (i.e. 1 <= 3 <= 4)
            parent = None
            if n.lineno < self.target_line:
                pre_block.append(n)
                previous = n
            # the line is contained with this
            elif n.lineno <= self.target_line <= n.end_lineno:
                on_line.append(n)
                parent = n
            # The target line can easily be skipped if there are comments or
            # white space or if the block is contained within another block.
            else:
                break

        # Capture the edge case when the block is contained within another.
        # These cases are explicitly restricted to If and other With blocks,
        # excluding by omission try, for, classes and functions.
        if len(on_line) == 0:
            if isinstance(previous, (ast.With, ast.If)):
                on_line.append(previous)
                # Captures both branches of If, and the With block.
                bodies = (
                    [previous.body]
                    if isinstance(previous, ast.With)
                    else [previous.body, previous.orelse]
                )
                for body in bodies:
                    try:
                        # Recursion by referring to the containing block also
                        # captures the case where the target line number was not
                        # exactly hit.
                        # for instance:
                        # 1 >>> if True:          # Captured ast node
                        # 2 >>>     with fn() as x:
                        # 3 >>>         with cache as c:
                        # 4 >>>             a = 1 # <<< frame line
                        # will recurse through here thrice to get to the frame
                        # line.
                        # NB. the "extracted" With block is the one that
                        # invoked this call
                        return ExtractWithBlock(
                            self.target_line
                        ).generic_visit(
                            body  # type: ignore[arg-type]
                        )
                    except BlockException:
                        pass

            else:
                raise BlockException(
                    "persistent_cache cannot be invoked within a block "
                    "(try moving the block within the persistent_cache scope)."
                )
        # Intentionally not elif (on_line can be added in previous block)
        if len(on_line) == 1:
            if parent and not isinstance(on_line[0], ast.With):
                raise BlockException("Detected line is not a With statement.")
            if not isinstance(on_line[0], ast.With):
                raise BlockException(
                    "Unconventional formatting may lead to unexpected behavior. "
                    "Please format your code, and/or reduce nesting.\n"
                    "For instance, the following is not supported:\n"
                    ">>>> with cache() as c: a = 1 # all one line"
                )
            return clean_to_modules(pre_block, on_line[0])
        # It should be possible to relate the lines with the AST,
        # but reduce potential bugs by just throwing an error.
        raise BlockException(
            "Unable to determine structure your call. Please"
            " report this to github:marimo-team/marimo/issues"
        )


class MangleArguments(ast.NodeTransformer):
    """Mangles arguments names to prevent shadowing issues in analysis."""

    def __init__(
        self,
        args: set[str],
        *arg: Any,
        prefix: str = ARG_PREFIX,
        **kwargs: Any,
    ) -> None:
        super().__init__(*arg, **kwargs)
        self.prefix = prefix
        self.args = args

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.args:
            node.id = f"{self.prefix}{node.id}"
        return node


class DeprivateVisitor(ast.NodeTransformer):
    """Removes the mangling of private variables from a module."""

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = unmangle_local(node.id).name
        return node

    def generic_visit(self, node: ast.AST) -> ast.AST:
        if hasattr(node, "name") and node.name:
            node.name = unmangle_local(node.name).name
        return super().generic_visit(node)


class RemoveReturns(ast.NodeTransformer):
    # NB: Won't work for generators since not replacing Yield.
    # Note that functools caches the generator, which is then dequeue'd,
    # so in that sense, it doesn't work either.
    def visit_Return(self, node: ast.Return) -> ast.Expr:
        expr = ast.Expr(value=node.value)
        expr.lineno = node.lineno
        expr.col_offset = node.col_offset
        return expr


def strip_function(fn: Callable[..., Any]) -> ast.Module:
    code, _ = inspect.getsourcelines(fn)
    args = set(fn.__code__.co_varnames)
    function_ast = ast.parse(textwrap.dedent("".join(code)))
    body = function_ast.body.pop()
    assert isinstance(body, (ast.FunctionDef, ast.AsyncFunctionDef)), (
        "Expected a function definition"
    )
    extracted = ast.Module(body.body, type_ignores=[])
    module = RemoveReturns().visit(extracted)
    module = MangleArguments(args).visit(module)
    assert isinstance(module, ast.Module), "Expected a module"
    return module
