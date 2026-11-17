# Copyright 2026 Marimo. All rights reserved.
"""Resolve cell-private names the way CPython's symbol table does.

marimo renames a cell-private name such as `_x` to a cell-specific global
wherever it refers to the cell's own top-level binding. Deciding that needs
every binding in a scope before any name in it can be resolved: a function
that assigns `_x` anywhere reads its own local `_x` everywhere, even above
the assignment. This module collects all bindings first and then resolves
each occurrence, so the renaming follows Python's rules instead of the
order in which the visitor happens to meet names.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class _Kind(Enum):
    MODULE = "module"
    FUNCTION = "function"
    CLASS = "class"
    COMPREHENSION = "comprehension"
    ANNOTATION = "annotation"


@dataclass(eq=False)
class _Scope:
    kind: _Kind
    parent: _Scope | None
    bound: set[str] = field(default_factory=set)
    declared_global: set[str] = field(default_factory=set)
    declared_nonlocal: set[str] = field(default_factory=set)
    # Names bound so far in a class body, in source order. A class body
    # reads its own namespace and then globals, so whether a read sees the
    # class binding depends on where it occurs.
    live: set[str] = field(default_factory=set)


@dataclass
class _Site:
    node: ast.AST
    name: str
    scope: _Scope
    binds: bool
    bound_in_class: bool = False
    forced_cell: bool = False


def find_cell_level_names(
    root: ast.AST, is_private: Callable[[str], bool]
) -> set[ast.AST]:
    """Return the nodes whose private name refers to the cell's binding.

    The result holds `ast.Name` nodes and the binding nodes that carry a
    name as a string (`def`, `class`, `import ... as`, `except ... as`, and
    `match` captures). Every other private-name occurrence refers to a
    function, class, comprehension, or annotation scope inside the cell.
    """
    collector = _Collector(is_private, _has_future_annotations(root))
    collector.collect(root)
    return {site.node for site in collector.sites if _refers_to_cell(site)}


def _has_future_annotations(root: ast.AST) -> bool:
    if not isinstance(root, ast.Module):
        return False
    for statement in root.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        if not (
            isinstance(statement, ast.ImportFrom)
            and statement.module == "__future__"
        ):
            return False
        if any(alias.name == "annotations" for alias in statement.names):
            return True
    return False


def _refers_to_cell(site: _Site) -> bool:
    if site.forced_cell:
        return True
    scope, name = site.scope, site.name
    if scope.kind is _Kind.MODULE or name in scope.declared_global:
        return True
    if name in scope.declared_nonlocal:
        return False
    if scope.kind is _Kind.CLASS:
        if site.binds:
            return False
        if name in scope.bound:
            return not site.bound_in_class
        return _free_refers_to_cell(scope.parent, name)
    if site.binds or name in scope.bound:
        return False
    parent = scope.parent
    if (
        scope.kind is _Kind.ANNOTATION
        and parent is not None
        and parent.kind is _Kind.CLASS
    ):
        # Unlike a method, an annotation scope honors its class's `global`,
        # and reads a name the class binds like the class body does: from
        # the class namespace and then globals, once the class body has run.
        if name in parent.declared_global:
            return True
        if name in parent.bound and name not in parent.declared_nonlocal:
            return name not in parent.live
    return _free_refers_to_cell(parent, name)


def _free_refers_to_cell(scope: _Scope | None, name: str) -> bool:
    """Resolve a free name; nested scopes do not see class bodies."""
    while scope is not None:
        if scope.kind is _Kind.MODULE:
            return True
        if scope.kind is not _Kind.CLASS:
            if name in scope.declared_global:
                return True
            if name in scope.bound or name in scope.declared_nonlocal:
                return False
        scope = scope.parent
    return True


class _Collector:
    def __init__(
        self, is_private: Callable[[str], bool], future_annotations: bool
    ) -> None:
        self.is_private = is_private
        self.future_annotations = future_annotations
        self.sites: list[_Site] = []
        self.scope = _Scope(_Kind.MODULE, None)

    def collect(self, root: ast.AST) -> None:
        if isinstance(root, ast.Module):
            self.statements(root.body)
        else:
            self.visit(root)

    # Recording

    def bind(self, name: str, node: ast.AST | None = None) -> None:
        self.bind_in(self.scope, name, node)

    def bind_in(
        self, scope: _Scope, name: str, node: ast.AST | None = None
    ) -> None:
        scope.bound.add(name)
        scope.live.add(name)
        if node is not None and self.is_private(name):
            self.sites.append(_Site(node, name, scope, binds=True))

    def unbind(self, name: str, node: ast.AST | None = None) -> None:
        """Record `del` or the end of an `except ... as` handler."""
        self.scope.bound.add(name)
        self.scope.live.discard(name)
        if node is not None and self.is_private(name):
            self.sites.append(_Site(node, name, self.scope, binds=True))

    def load(self, node: ast.Name) -> None:
        if self.is_private(node.id):
            self.sites.append(
                _Site(
                    node,
                    node.id,
                    self.scope,
                    binds=False,
                    bound_in_class=node.id in self.scope.live,
                )
            )

    def push(self, kind: _Kind) -> _Scope:
        self.scope = _Scope(kind, self.scope)
        return self.scope

    def pop(self, scope: _Scope) -> None:
        assert self.scope is scope
        assert scope.parent is not None
        self.scope = scope.parent

    # Traversal

    def statements(self, body: Iterable[ast.stmt]) -> None:
        for statement in body:
            self.visit(statement)

    def visit(self, node: ast.AST | None) -> None:
        if node is None:
            return
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is not None:
            method(node)
        else:
            for child in ast.iter_child_nodes(node):
                self.visit(child)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.bind(node.id, node)
        elif isinstance(node.ctx, ast.Del):
            self.unbind(node.id, node)
        else:
            self.load(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.scope.declared_global.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.scope.declared_nonlocal.update(node.names)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.value)
        if self.scope.kind is _Kind.FUNCTION:
            # Function-body annotations are never evaluated.
            self.visit(node.annotation)
        else:
            self.annotation(node.annotation)
        if isinstance(node.target, ast.Name):
            was_live = node.target.id in self.scope.live
            self.bind(node.target.id, node.target)
            if node.value is None and not was_live:
                # A bare annotation makes the name local without a value.
                self.scope.live.discard(node.target.id)
        else:
            self.visit(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        target = self.scope
        while target.kind in (_Kind.COMPREHENSION, _Kind.ANNOTATION):
            assert target.parent is not None
            target = target.parent
        self.bind_in(target, node.target.id, node.target)

    def visit_Import(self, node: ast.Import) -> None:
        self.aliases(node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.aliases(node.names)

    def aliases(self, names: list[ast.alias]) -> None:
        for alias in names:
            if alias.asname is not None:
                self.bind(alias.asname, alias)
            elif alias.name != "*":
                # marimo never renames a bare import; it still binds.
                self.bind(alias.name.split(".")[0])

    def visit_Try(self, node: ast.Try | ast.TryStar) -> None:
        self.statements(node.body)
        for handler in node.handlers:
            self.visit(handler.type)
            if handler.name is not None:
                self.bind(handler.name, handler)
            self.statements(handler.body)
            if handler.name is not None:
                self.unbind(handler.name)
        self.statements(node.orelse)
        self.statements(node.finalbody)

    visit_TryStar = visit_Try

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        self.visit(node.pattern)
        if node.name is not None:
            self.bind(node.name, node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self.bind(node.name, node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        for key in node.keys:
            self.visit(key)
        for pattern in node.patterns:
            self.visit(pattern)
        if node.rest is not None:
            self.bind(node.rest, node)

    def annotation(self, node: ast.expr | None) -> None:
        """Visit an annotation that Python evaluates (or would evaluate)."""
        if node is None:
            return
        if self.future_annotations:
            # Annotations stay strings, which `typing.get_type_hints`
            # evaluates in the module globals.
            start = len(self.sites)
            self.visit(node)
            for site in self.sites[start:]:
                site.forced_cell = True
        elif sys.version_info >= (3, 14):
            scope = self.push(_Kind.ANNOTATION)
            self.visit(node)
            self.pop(scope)
        else:
            self.visit(node)

    def type_params(self, node: ast.AST) -> _Scope | None:
        params = getattr(node, "type_params", None)
        if not params:
            return None
        scope = self.push(_Kind.ANNOTATION)
        for param in params:
            self.bind(param.name)
        for param in params:
            for child in ast.iter_child_nodes(param):
                self.visit(child)
        return scope

    def visit_FunctionDef(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.defaults(node.args)
        generic = self.type_params(node)
        for arg in _arguments(node.args):
            self.annotation(arg.annotation)
        self.annotation(node.returns)
        body = self.push(_Kind.FUNCTION)
        for arg in _arguments(node.args):
            self.bind(arg.arg)
        self.statements(node.body)
        self.pop(body)
        if generic is not None:
            self.pop(generic)
        self.bind(node.name, node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.defaults(node.args)
        body = self.push(_Kind.FUNCTION)
        for arg in _arguments(node.args):
            self.bind(arg.arg)
        self.visit(node.body)
        self.pop(body)

    def defaults(self, args: ast.arguments) -> None:
        for default in (*args.defaults, *args.kw_defaults):
            self.visit(default)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        generic = self.type_params(node)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)
        body = self.push(_Kind.CLASS)
        self.statements(node.body)
        self.pop(body)
        if generic is not None:
            self.pop(generic)
        self.bind(node.name, node)

    if sys.version_info >= (3, 12):

        def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
            generic = self.type_params(node)
            lazy = self.push(_Kind.ANNOTATION)
            self.visit(node.value)
            self.pop(lazy)
            if generic is not None:
                self.pop(generic)
            self.visit(node.name)

    def comprehension(
        self, node: ast.expr, generators: list[ast.comprehension]
    ) -> None:
        # The first iterable is evaluated in the enclosing scope.
        self.visit(generators[0].iter)
        scope = self.push(_Kind.COMPREHENSION)
        for index, generator in enumerate(generators):
            if index:
                self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            assert isinstance(
                node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)
            )
            self.visit(node.elt)
        self.pop(scope)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.comprehension(node, node.generators)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.comprehension(node, node.generators)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.comprehension(node, node.generators)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.comprehension(node, node.generators)


def _arguments(args: ast.arguments) -> list[ast.arg]:
    return [
        arg
        for arg in (
            *args.posonlyargs,
            *args.args,
            args.vararg,
            *args.kwonlyargs,
            args.kwarg,
        )
        if arg is not None
    ]
