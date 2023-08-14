# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

Name = str


def _is_local(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


@dataclass
class Block:
    """A scope in which names are declared."""

    # Defined names
    defs: set[Name] = field(default_factory=set)
    # Names defined with the global keyword
    global_names: set[Name] = field(default_factory=set)
    # Comprehensions have special scoping rules
    is_comprehension: bool = False


@dataclass
class RefData:
    """Metadata about variables referenced but not defined by a cell"""

    # Whether the ref was deleted
    deleted: bool
    # Ancestors of the block in which this ref was used
    parent_blocks: list[Block]


class ScopedVisitor(ast.NodeVisitor):
    def __init__(self, mangle_prefix: Optional[str] = None) -> None:
        self.block_stack: list[Block] = [Block()]
        # Mapping from referenced names to their metadata
        self._refs: dict[Name, RefData] = {}
        # Unique prefix used to mangle cell-local variable names
        self.id = (
            str(uuid4()).replace("-", "_")
            if mangle_prefix is None
            else mangle_prefix
        )

    @property
    def refs(self) -> set[Name]:
        """Names referenced but not defined."""
        return set(self._refs.keys())

    @property
    def deleted_refs(self) -> set[Name]:
        """Referenced names that were deleted with `del`."""
        return set(name for name in self._refs if self._refs[name].deleted)

    def _if_local_then_mangle(
        self, name: str, ignore_scope: bool = False
    ) -> str:
        """Mangle local variable name declared at top-level scope."""
        if _is_local(name) and (len(self.block_stack) == 1 or ignore_scope):
            return f"_{self.id}{name}"
        else:
            return name

    def _is_defined(self, identifier: str) -> bool:
        """Check if `identifier` is defined in any block."""
        return any(identifier in block.defs for block in self.block_stack)

    def _add_ref(self, name: Name, deleted: bool) -> None:
        """Register a referenced name."""
        self._refs[name] = RefData(
            deleted=deleted,
            parent_blocks=self.block_stack[:-1],
        )

    def _remove_ref(self, name: Name) -> None:
        """Remove a referenced name."""
        del self._refs[name]

    def _define(self, name: Name) -> None:
        """Define a name in the current block.

        Names created with the global keyword are added to the top-level
        (global scope) block.
        """
        # If `name` is added to the top-level block, it is also evicted from
        # any captured refs (if present) --- this handles cases where a name is
        # encountered and captured before it is declared, such as in
        #
        # ```
        # def f():
        #   print(x)
        # x = 0
        # ```
        block_idx = 0 if name in self.block_stack[-1].global_names else -1
        self.block_stack[block_idx].defs.add(name)
        if (
            name in self._refs
            and self.block_stack[block_idx] in self._refs[name].parent_blocks
        ):
            # `name` was used as a capture, not a reference
            self._remove_ref(name)

    def _push_block(self, is_comprehension: bool) -> None:
        """Push a block onto the block stack."""
        self.block_stack.append(Block(is_comprehension=is_comprehension))

    def _pop_block(self) -> None:
        """Pop a block from the block stack."""
        self.block_stack.pop()

    @property
    def defs(self) -> set[Name]:
        """Get all global defs."""
        return self.block_stack[0].defs

    def generic_visit(self, node: ast.AST) -> None:
        """Visits the children of node and manages the block stack.

        Note: visit calls visit_ClassName, or generic_visit() if the former
        doesn't exist. That means that _this method should never call
        visit on `node`_, as this could lead to unbounded recursion.
        (Calling visit on `node`'s children is fine.) In summary:
        call super().generic_visit on `node` and `visit()` on node's children.
        """
        if isinstance(
            node,
            (ast.ClassDef, ast.AsyncFunctionDef, ast.FunctionDef, ast.Lambda),
        ):
            # These AST nodes introduce a new scope, but otherwise do not
            # require special treatment.
            self._push_block(is_comprehension=False)
            super().generic_visit(node)
            self._pop_block()
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            # In comprehensions, generators must be visited before elements
            # because generators define local targets that elements may use.
            self._push_block(is_comprehension=True)
            for generator in node.generators:
                self.visit(generator)
            self.visit(node.elt)
            self._pop_block()
        elif isinstance(node, ast.DictComp):
            # Special-cased for the same reason that other comprehensions are
            # special-cased.
            self._push_block(is_comprehension=True)
            for generator in node.generators:
                self.visit(generator)
            self.visit(node.value)
            self.visit(node.key)
            self._pop_block()
        else:
            # Other nodes that don't introduce a new scope
            super().generic_visit(node)

    # ClassDef and FunctionDef nodes don't have ast.Name nodes as children
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(Name(node.name))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(node.name)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        node.arg = self._if_local_then_mangle(node.arg)
        self._define(node.arg)
        if node.annotation is not None:
            self.visit(node.annotation)

    def visit_arguments(self, node: ast.arguments) -> None:
        # process potential refs before defs, to handle patterns like
        #
        # def f(x=x):
        #   ...
        for v in node.kw_defaults:
            if v is not None:
                self.visit(v)
        for v in node.defaults:
            if v is not None:
                self.visit(v)

        for arg in node.posonlyargs:
            self.visit(arg)
        for arg in node.args:
            self.visit(arg)
        for arg in node.kwonlyargs:
            self.visit(arg)
        if node.vararg is not None:
            self.visit(node.vararg)
        if node.kwarg is not None:
            self.visit(node.kwarg)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Visit the value first, to handle cases like
        #
        # class A:
        #   x = x
        #
        # Handling value first is required to register `x` as a ref.
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self.visit(node.target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
        self.visit(node.annotation)
        self.visit(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        if self.block_stack[-1].is_comprehension and isinstance(
            node.target, ast.Name
        ):
            for block in reversed(self.block_stack):
                if not block.is_comprehension:
                    node.target.id = self._if_local_then_mangle(
                        node.target.id,
                        ignore_scope=(block == self.block_stack[0]),
                    )
                    block.defs.add(node.target.id)
                    break
        else:
            self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # NB: AugAssign has a Store ctx; this means that mutating a var
        # will create a def, which we can catch as an error later if
        # that var was defined by another cell
        #
        # NB: Only mangle loaded or deleted names if they are local
        # and found to be referring to a top-level variable. This prevents
        # us from mangling references to variables names conforming to local
        # spec but declared in a nested scope.
        #
        # NB: we don't implement visit_Attribute because refs and defs
        # are not tracked at the attribute level. The default behavior
        # with our implemented visitors does the right thing (foo.bar[.*]
        # generates a ref to foo if foo has not been def'd).
        if isinstance(node.ctx, ast.Store):
            node.id = self._if_local_then_mangle(node.id)
            self._define(node.id)
        elif (
            isinstance(node.ctx, ast.Load)
            and not self._is_defined(node.id)
            and not _is_local(node.id)
        ):
            self._add_ref(node.id, deleted=False)
        elif (
            isinstance(node.ctx, ast.Del)
            and not self._is_defined(node.id)
            and not _is_local(node.id)
        ):
            self._add_ref(node.id, deleted=True)
        elif _is_local(node.id):
            mangled_name = self._if_local_then_mangle(
                node.id, ignore_scope=True
            )
            for block in reversed(self.block_stack):
                if block == self.block_stack[0] and mangled_name in block.defs:
                    node.id = mangled_name
                elif node.id in block.defs:
                    break

        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        node.names = [
            self._if_local_then_mangle(name, ignore_scope=True)
            for name in node.names
        ]
        for name in node.names:
            self.block_stack[-1].global_names.add(name)

    # TODO(akshayka): can we find a way around tracking imports as state
    # that needs to be tracked?
    # Import and ImportFrom statements have symbol names in alias nodes
    def visit_alias(self, node: ast.alias) -> None:
        if node.asname is None:
            node.name = self._if_local_then_mangle(node.name)
            self._define(node.name)
        else:
            node.asname = self._if_local_then_mangle(node.asname)
            self._define(node.asname)
        self.generic_visit(node)

    if sys.version_info >= (3, 10):
        # Match statements were introduced in Python 3.10
        #
        # Top-level match statements are awkward in marimo --- at parse-time,
        # we have to register all names in every case/pattern as globals (since
        # we don't know the value of the match subject), even though only a
        # subset of the names will be bound at runtime. For this reason, in
        # marimo, match statements should really only be used in local scopes.
        def visit_MatchAs(self, node: ast.MatchAs) -> None:
            if node.name is not None:
                node.name = self._if_local_then_mangle(node.name)
                self._define(node.name)
            if node.pattern is not None:
                # pattern may contain additional MatchAs statements in it
                self.visit(node.pattern)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest is not None:
                node.rest = self._if_local_then_mangle(node.rest)
                self._define(node.rest)
            for key in node.keys:
                self.visit(key)
            for pattern in node.patterns:
                self.visit(pattern)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name is not None:
                node.name = self._if_local_then_mangle(node.name)
                self._define(node.name)
