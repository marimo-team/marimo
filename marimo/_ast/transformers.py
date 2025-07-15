# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import inspect
import textwrap
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

from marimo._ast.variables import unmangle_local

if TYPE_CHECKING:
    from collections.abc import Sequence

ARG_PREFIX: str = "*"


class BlockException(Exception):
    pass


def compiled_ast(block: Sequence[ast.AST | ast.stmt]) -> ast.Module:
    return cast(
        ast.Module,
        compile(
            ast.Module(cast(list[ast.stmt], block), type_ignores=[]),
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
            value=cast(ast.expr, initializer),
        )
    else:
        # Edgecase with no "as" clause.
        initializer = ast.Expr(value=cast(ast.expr, initializer))
    initializer.lineno = len(pre_block) + 1
    initializer.col_offset = 0
    pre_block.append(initializer)
    return (compiled_ast(pre_block), compiled_ast(block.body))


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


class NameTransformer(ast.NodeTransformer):
    def __init__(self, name_substitutions: dict[str, str]) -> None:
        """Remaps names in an AST.

        Naively remaps all occurrences of names in an AST, given a substitution
        dict mapping old names to new names. In particular does not take
        scoping into account.
        """
        self._name_substitutions = name_substitutions
        self.made_changes = False
        super().__init__()

    def visit_Name(self, node: ast.Name) -> ast.Name:
        self.generic_visit(node)
        if node.id in self._name_substitutions:
            self.made_changes = True
            return ast.Name(
                **{**node.__dict__, "id": self._name_substitutions[node.id]}
            )
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        if node.name in self._name_substitutions:
            self.made_changes = True
            return ast.FunctionDef(
                **{
                    **node.__dict__,
                    "name": self._name_substitutions[node.name],
                }
            )
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        if node.name in self._name_substitutions:
            self.made_changes = True
            return ast.AsyncFunctionDef(
                **{
                    **node.__dict__,
                    "name": self._name_substitutions[node.name],
                }
            )
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.generic_visit(node)
        if node.name in self._name_substitutions:
            self.made_changes = True
            return ast.ClassDef(
                **{
                    **node.__dict__,
                    "name": self._name_substitutions[node.name],
                }
            )
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        self.generic_visit(node)
        new_targets: list[Any] = []
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id in self._name_substitutions
            ):
                self.made_changes = True
                new_targets.append(
                    ast.Name(
                        id=self._name_substitutions[target.id], ctx=ast.Store()
                    )
                )
            else:
                new_targets.append(target)
        return ast.Assign(
            **{
                **node.__dict__,
                "targets": new_targets,
            }
        )


class RemoveImportTransformer(ast.NodeTransformer):
    """Removes import that matches the given name.
    e.g. given import_name = "bar":
    ```python
    from foo import bar  # removed
    from foo import bar as baz
    import foo.bar
    import foo.bar as baz
    import foo.baz as bar  # removed
    ```
    To prevent module collisions in top level definitions.
    """

    def __init__(self, import_name: str) -> None:
        super().__init__()
        self.import_name = import_name

    def strip_imports(self, code: str) -> str:
        tree = ast.parse(code)
        tree = self.visit(tree)
        return ast.unparse(tree).strip()

    def visit_Import(self, node: ast.Import) -> Optional[ast.Import]:
        name = self.import_name
        node.names = [
            alias
            for alias in node.names
            if (alias.asname and alias.asname != name)
            or (not alias.asname and alias.name != name)
        ]
        return node if node.names else None

    def visit_ImportFrom(
        self, node: ast.ImportFrom
    ) -> Optional[ast.ImportFrom]:
        name = self.import_name
        node.names = [
            alias
            for alias in node.names
            if (alias.asname and alias.asname != name)
            or (not alias.asname and alias.name != name)
        ]
        return node if node.names else None


class ExtractWithBlock(ast.NodeTransformer):
    def __init__(
        self,
        line: int,
        allowed_types: tuple[type, ...],
        *arg: Any,
        name: str = "context",
        **kwargs: Any,
    ) -> None:
        super().__init__(*arg, **kwargs)
        self.target_line = line
        if not allowed_types:
            allowed_types = (ast.With,)
        self.allowed_types = allowed_types
        self.name = name

    def generic_visit(self, node: ast.AST) -> tuple[ast.Module, ast.Module]:  # type: ignore[override]
        pre_block = []

        # There are a few strange edges cases like:
        # >>> with open("file.txt"): pass
        #
        # It's difficult to properly delineate the block, so if multiple
        # things map to the same line number, it's best to throw an error.
        on_line = []
        previous = None

        assert isinstance(node, list), "Unexpected block structure."
        parent = None
        for n in node:
            # There's a chance that the block is first evaluated somewhere in a
            # multiline line expression, for instance:
            # 1 >>> with cache as c:
            # 2 >>>    a = [
            # 3 >>>        f(x) # <<< first frame call is here, and not line 2
            # 4 >>>    ]
            # so check that the "target" line is in the interval
            # (i.e. 1 <= 3 <= 4)
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
            if isinstance(
                previous,
                self.allowed_types,
            ):
                on_line.append(previous)
                # Captures both branches of If, and the With block.
                bodies = (
                    [previous.body, previous.orelse]
                    if isinstance(previous, ast.If)
                    else [previous.body]  # type: ignore[attr-defined]
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
                            self.target_line,
                            self.allowed_types,
                            name=self.name,
                        ).generic_visit(
                            body  # type: ignore[arg-type]
                        )
                    except BlockException:
                        pass

            else:
                raise BlockException(
                    f"{self.name} cannot be invoked within a {type(previous)} "
                    f"block (try moving the block within the {self.name} "
                    "scope)."
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
                    f">>>> with {self.name}: a = 1 # all one line"
                )
            return clean_to_modules(pre_block, on_line[0])
        # It should be possible to relate the lines with the AST,
        # but reduce potential bugs by just throwing an error.
        raise BlockException(
            "Unable to determine structure your call. Please"
            " report this to github:marimo-team/marimo/issues"
        )


class CacheExtractWithBlock(ExtractWithBlock):
    def __init__(self, line: int, *arg: Any, **kwargs: Any) -> None:
        name = kwargs.pop("name", "cache")
        super().__init__(line, (ast.With, ast.If), *arg, name=name, **kwargs)

    def generic_visit(self, node: ast.AST) -> tuple[ast.Module, ast.Module]:  # type: ignore[override]
        pre_block, with_block = super().generic_visit(node)
        # We should fail if the first node in with_block is a try.
        if isinstance(with_block.body[0], ast.Try):
            raise BlockException(
                "As a limitation of caching context, the first statement "
                "cannot be a try block."
                "\n"
                "Please move the cache block inside of the try, or use a start "
                "the block with a different statement."
                "\n"
                "Note, exceptions have cache invalidating consequences (by "
                "virtue of side effects), and handling exceptions in the "
                "cache block may lead to unexpected behavior."
            )
        return (pre_block, with_block)


class ContainedExtractWithBlock(ExtractWithBlock):
    def __init__(self, line: int, *arg: Any, **kwargs: Any) -> None:
        name = kwargs.pop("name", "app.setup")
        super().__init__(
            line,
            (
                ast.With,
                ast.If,
                ast.FunctionDef,
                ast.ClassDef,
                ast.AsyncFunctionDef,
            ),
            *arg,
            name=name,
            **kwargs,
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
        expr = ast.Expr(value=cast(ast.expr, node.value))
        expr.lineno = node.lineno
        expr.col_offset = node.col_offset
        return expr
