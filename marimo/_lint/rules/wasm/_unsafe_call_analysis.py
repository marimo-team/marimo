# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from marimo._ast.visitor import ImportData

# Functions that trap at runtime even though their parent module imports fine.
UNSAFE_ATTR_CALLS: dict[str, set[str]] = {
    "os": {
        "system",
        "popen",
        "fork",
        "kill",
        "killpg",
        "getuid",
        "getgid",
    },
    "signal": {"signal", "alarm"},
    "multiprocessing": {
        "Array",
        "Barrier",
        "BoundedSemaphore",
        "Condition",
        "Event",
        "JoinableQueue",
        "Lock",
        "Manager",
        "Pipe",
        "RLock",
        "RawArray",
        "RawValue",
        "Semaphore",
        "Value",
    },
    "multiprocessing.context": {
        "Array",
        "Barrier",
        "BoundedSemaphore",
        "Condition",
        "Event",
        "ForkContext",
        "ForkProcess",
        "ForkServerContext",
        "ForkServerProcess",
        "JoinableQueue",
        "Lock",
        "Manager",
        "Pipe",
        "RLock",
        "RawArray",
        "RawValue",
        "Semaphore",
        "Value",
    },
    "multiprocessing.pool": {"ThreadPool"},
    "multiprocessing.queues": {"JoinableQueue"},
}

# Prefixes for os.exec*, os.spawn* families.
UNSAFE_ATTR_PREFIXES: dict[str, tuple[str, ...]] = {
    "os": ("exec", "spawn"),
}

UNSAFE_START_METHOD_CALLS = frozenset(
    {
        "multiprocessing.get_context",
        "multiprocessing.set_start_method",
    }
)

UNSAFE_BUILTINS = frozenset({"breakpoint"})

MULTIPROCESSING_CONTEXT_ALIAS = "multiprocessing.context"

_MISSING = object()


@dataclass(frozen=True)
class _ValueAliases:
    module: str | None = None
    call: str | None = None
    start_method: str | None = None


def _record_module_alias(
    module_aliases: dict[str, str],
    *,
    module: str,
    definition: str,
) -> None:
    top_level = module.split(".", maxsplit=1)[0]
    if definition == top_level:
        module_aliases[definition] = top_level
        return
    module_aliases[definition] = module


def _record_symbol_alias(
    module_aliases: dict[str, str],
    call_aliases: dict[str, str],
    start_method_aliases: dict[str, str],
    *,
    module: str,
    definition: str,
    imported_symbol: str,
) -> None:
    attr = imported_symbol.removeprefix(f"{module}.")
    unsafe_calls = UNSAFE_ATTR_CALLS.get(module, set())
    unsafe_prefixes = UNSAFE_ATTR_PREFIXES.get(module, ())
    if "." not in attr and (
        attr in unsafe_calls
        or any(attr.startswith(p) for p in unsafe_prefixes)
    ):
        call_aliases[definition] = imported_symbol

    if imported_symbol in UNSAFE_ATTR_CALLS:
        module_aliases[definition] = imported_symbol

    if imported_symbol in UNSAFE_START_METHOD_CALLS:
        start_method_aliases[definition] = imported_symbol


def record_import_data_alias(
    module_aliases: dict[str, str],
    call_aliases: dict[str, str],
    start_method_aliases: dict[str, str],
    import_data: ImportData,
) -> None:
    if import_data.import_level not in (None, 0):
        return

    if import_data.imported_symbol is None:
        _record_module_alias(
            module_aliases,
            module=import_data.module,
            definition=import_data.definition,
        )
        return

    _record_symbol_alias(
        module_aliases,
        call_aliases,
        start_method_aliases,
        module=import_data.module,
        definition=import_data.definition,
        imported_symbol=import_data.imported_symbol,
    )


def _argument_names(arguments: ast.arguments) -> set[str]:
    names = {
        arg.arg
        for arg in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


class _BindingCollector(ast.NodeVisitor):
    """Collect names that are local to a function body."""

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.global_names: set[str] = set()

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.global_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        del node

    def visit_ListComp(self, node: ast.ListComp) -> None:
        del node

    def visit_SetComp(self, node: ast.SetComp) -> None:
        del node

    def visit_DictComp(self, node: ast.DictComp) -> None:
        del node

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        del node

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(
                alias.asname or alias.name.split(".", maxsplit=1)[0]
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.names.add(alias.asname or alias.name)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)


def _function_bound_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    collector = _BindingCollector()
    for statement in node.body:
        collector.visit(statement)
    return (
        _argument_names(node.args) | collector.names
    ) - collector.global_names


class UnsafeCallVisitor(ast.NodeVisitor):
    """Collect unsafe calls with their line/column info."""

    def __init__(
        self,
        *,
        module_aliases: dict[str, str] | None = None,
        call_aliases: dict[str, str] | None = None,
        start_method_aliases: dict[str, str] | None = None,
        bound_names: set[str] | None = None,
    ) -> None:
        self.findings: list[tuple[int, int, str]] = []
        self.module_alias_scopes = [dict(module_aliases or {})]
        self.call_alias_scopes = [dict(call_aliases or {})]
        self.start_method_alias_scopes = [dict(start_method_aliases or {})]
        self.bound_scopes: list[set[str]] = [set(bound_names or set())]
        self.scope_kinds = ["module"]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_definition(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_definition(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        self._push_scope(_argument_names(node.args), kind="function")
        try:
            self.visit(node.body)
        finally:
            self._pop_scope()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)

        self._push_scope(set(), kind="class")
        try:
            for statement in node.body:
                if isinstance(
                    statement,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    self._visit_class_method_definition(statement, node.name)
                else:
                    self.visit(statement)
        finally:
            self._pop_scope()
        self._bind_name(node.name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            definition = alias.asname or alias.name.split(".", maxsplit=1)[0]
            self._bind_name(definition)
            _record_module_alias(
                self.module_alias_scopes[-1],
                module=alias.name,
                definition=definition,
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            for alias in node.names:
                self._bind_name(alias.asname or alias.name)
            return
        if node.module is None:
            return

        for alias in node.names:
            local_name = alias.asname or alias.name
            self._bind_name(local_name)
            _record_symbol_alias(
                self.module_alias_scopes[-1],
                self.call_alias_scopes[-1],
                self.start_method_alias_scopes[-1],
                module=node.module,
                definition=local_name,
                imported_symbol=f"{node.module}.{alias.name}",
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self._bind_assignment_target(target, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            self.visit(node.annotation)
            self._bind_target(
                node.target,
                value_aliases=self._aliases_for_value(node.value),
            )
            return
        self.visit(node.annotation)
        self._visit_target_expression(node.target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self._bind_target(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind_target(
            node.target,
            value_aliases=self._aliases_for_value(node.value),
        )

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        self._visit_branch(node.body)
        self._visit_branch(node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self._visit_for_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for_loop(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with_block(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with_block(node)

    def _visit_for_loop(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        snapshot = self._snapshot_scopes()
        self._bind_target(node.target)
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            loop_result = self._snapshot_scopes()
            self._restore_scopes(snapshot)
            self._merge_aliases_from_snapshot(loop_result)
        self._visit_branch(node.orelse)

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        self._visit_branch(node.body)
        self._visit_branch(node.orelse)

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_branch(node.body)
        for handler in node.handlers:
            self._visit_branch([handler])
        self._visit_branch(node.orelse)
        self._visit_branch(node.finalbody)

    def _visit_with_block(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind_target(item.optional_vars)
        for statement in node.body:
            self.visit(statement)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is not None:
            self.visit(node.type)
        if node.name is not None:
            self._bind_name(node.name)
        for statement in node.body:
            self.visit(statement)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, (node.key, node.value))

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, (node.elt,))

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            call_name = self._unsafe_attribute_call(node.func)
            if call_name is not None:
                self.findings.append((node.lineno, node.col_offset, call_name))
            else:
                call_path = self._resolve_path(node.func)
                start_method_call = self._unsafe_start_method_call(
                    node,
                    call_path,
                )
                if start_method_call is not None:
                    self.findings.append(
                        (node.lineno, node.col_offset, start_method_call)
                    )

        elif isinstance(node.func, ast.Name):
            call_name = self._lookup_call_alias(node.func.id)
            if call_name is not None:
                self.findings.append(
                    (node.lineno, node.col_offset, f"{call_name}()")
                )
            else:
                start_method_alias = self._lookup_start_method_alias(
                    node.func.id
                )
                if start_method_alias is not None:
                    start_method_call = self._unsafe_start_method_call(
                        node,
                        start_method_alias,
                    )
                    if start_method_call is not None:
                        self.findings.append(
                            (node.lineno, node.col_offset, start_method_call)
                        )
            if (
                call_name is None
                and node.func.id in UNSAFE_BUILTINS
                and not self._is_bound_name(node.func.id)
            ):
                self.findings.append(
                    (node.lineno, node.col_offset, f"{node.func.id}()")
                )

        self.generic_visit(node)

    def _visit_function_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._visit_function_header(node)
        self._bind_name(node.name)
        self._visit_function_body(node)

    def _visit_class_method_definition(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str,
    ) -> None:
        self._visit_function_header(node)
        self._bind_name(node.name)
        binding_scope = self._class_binding_scope_index()
        if binding_scope is None:
            self._visit_function_body(node)
            return

        restore = self._temporarily_bind_name(binding_scope, class_name)
        try:
            self._visit_function_body(node)
        finally:
            restore()

    def _visit_function_header(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self._visit_argument_annotations(node.args)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        if node.returns is not None:
            self.visit(node.returns)

    def _visit_argument_annotations(self, arguments: ast.arguments) -> None:
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ):
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if (
            arguments.vararg is not None
            and arguments.vararg.annotation is not None
        ):
            self.visit(arguments.vararg.annotation)
        if (
            arguments.kwarg is not None
            and arguments.kwarg.annotation is not None
        ):
            self.visit(arguments.kwarg.annotation)

    def _visit_function_body(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._push_scope(_function_bound_names(node), kind="function")
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self._pop_scope()

    def _visit_comprehension(
        self,
        generators: list[ast.comprehension],
        result_nodes: tuple[ast.AST, ...],
    ) -> None:
        self._push_scope(set(), kind="function")
        try:
            for generator in generators:
                self.visit(generator.iter)
                self._bind_target(generator.target)
                for condition in generator.ifs:
                    self.visit(condition)
            for result_node in result_nodes:
                self.visit(result_node)
        finally:
            self._pop_scope()

    def _visit_branch(self, statements: Sequence[ast.AST]) -> None:
        snapshot = self._snapshot_scopes()
        try:
            for statement in statements:
                self.visit(statement)
        finally:
            branch_result = self._snapshot_scopes()
            self._restore_scopes(snapshot)
            self._merge_aliases_from_snapshot(branch_result)

    def _snapshot_scopes(
        self,
    ) -> tuple[
        list[dict[str, str]],
        list[dict[str, str]],
        list[dict[str, str]],
        list[set[str]],
        list[str],
    ]:
        return (
            [dict(scope) for scope in self.module_alias_scopes],
            [dict(scope) for scope in self.call_alias_scopes],
            [dict(scope) for scope in self.start_method_alias_scopes],
            [set(scope) for scope in self.bound_scopes],
            list(self.scope_kinds),
        )

    def _restore_scopes(
        self,
        snapshot: tuple[
            list[dict[str, str]],
            list[dict[str, str]],
            list[dict[str, str]],
            list[set[str]],
            list[str],
        ],
    ) -> None:
        (
            self.module_alias_scopes,
            self.call_alias_scopes,
            self.start_method_alias_scopes,
            self.bound_scopes,
            self.scope_kinds,
        ) = snapshot

    def _merge_aliases_from_snapshot(
        self,
        snapshot: tuple[
            list[dict[str, str]],
            list[dict[str, str]],
            list[dict[str, str]],
            list[set[str]],
            list[str],
        ],
    ) -> None:
        module_scopes, call_scopes, start_method_scopes, _, _ = snapshot
        scope_count = min(len(self.module_alias_scopes), len(module_scopes))
        for index in range(scope_count):
            for name, module in module_scopes[index].items():
                if module in UNSAFE_ATTR_CALLS:
                    self.module_alias_scopes[index][name] = module
            self.call_alias_scopes[index].update(call_scopes[index])
            self.start_method_alias_scopes[index].update(
                start_method_scopes[index]
            )

    def _push_scope(self, bound_names: set[str], *, kind: str) -> None:
        self.module_alias_scopes.append({})
        self.call_alias_scopes.append({})
        self.start_method_alias_scopes.append({})
        self.bound_scopes.append(set(bound_names))
        self.scope_kinds.append(kind)

    def _pop_scope(self) -> None:
        self.module_alias_scopes.pop()
        self.call_alias_scopes.pop()
        self.start_method_alias_scopes.pop()
        self.bound_scopes.pop()
        self.scope_kinds.pop()

    def _bind_target(
        self,
        node: ast.AST,
        *,
        value_aliases: _ValueAliases | None = None,
    ) -> None:
        if isinstance(node, ast.Name):
            self._bind_name(node.id)
            if value_aliases is not None:
                if value_aliases.module is not None:
                    self.module_alias_scopes[-1][node.id] = (
                        value_aliases.module
                    )
                if value_aliases.call is not None:
                    self.call_alias_scopes[-1][node.id] = value_aliases.call
                if value_aliases.start_method is not None:
                    self.start_method_alias_scopes[-1][node.id] = (
                        value_aliases.start_method
                    )
        elif isinstance(node, ast.Starred):
            self._bind_target(node.value)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for element in node.elts:
                self._bind_target(element)
        elif isinstance(node, ast.Attribute):
            self.visit(node.value)
        elif isinstance(node, ast.Subscript):
            self.visit(node.value)
            self.visit(node.slice)

    def _bind_assignment_target(
        self,
        target: ast.AST,
        value: ast.AST,
    ) -> None:
        if (
            isinstance(target, (ast.Tuple, ast.List))
            and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)
        ):
            for target_element, value_element in zip(
                target.elts,
                value.elts,
                strict=True,
            ):
                self._bind_assignment_target(target_element, value_element)
            return

        self._bind_target(target, value_aliases=self._aliases_for_value(value))

    def _visit_target_expression(self, node: ast.AST) -> None:
        if isinstance(node, ast.Attribute):
            self.visit(node.value)
        elif isinstance(node, ast.Subscript):
            self.visit(node.value)
            self.visit(node.slice)
        elif isinstance(node, ast.Starred):
            self._visit_target_expression(node.value)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for element in node.elts:
                self._visit_target_expression(element)

    def _aliases_for_value(self, node: ast.AST) -> _ValueAliases:
        if isinstance(node, ast.Name):
            call_alias = self._lookup_call_alias(node.id)
            if call_alias is not None:
                return _ValueAliases(call=call_alias)
            start_method_alias = self._lookup_start_method_alias(node.id)
            if start_method_alias is not None:
                return _ValueAliases(start_method=start_method_alias)
            module_alias = self._lookup_module_alias(node.id)
            if module_alias in UNSAFE_ATTR_CALLS:
                return _ValueAliases(module=module_alias)
            return _ValueAliases()

        if isinstance(node, ast.Attribute):
            full_path = self._resolve_path(node)
            if full_path is None:
                return _ValueAliases()
            if full_path in UNSAFE_ATTR_CALLS:
                return _ValueAliases(module=full_path)
            unsafe_call = self._unsafe_call_alias_for_path(full_path)
            if unsafe_call is not None:
                return _ValueAliases(call=unsafe_call)
            if full_path in UNSAFE_START_METHOD_CALLS:
                return _ValueAliases(start_method=full_path)
            return _ValueAliases()

        if not isinstance(node, ast.Call):
            return _ValueAliases()

        call_path = self._resolve_call_path(node.func)
        if call_path != "multiprocessing.get_context":
            return _ValueAliases()

        method = self._start_method_literal(node)
        if method is not None and method != "spawn":
            return _ValueAliases()

        return _ValueAliases(module=MULTIPROCESSING_CONTEXT_ALIAS)

    def _resolve_call_path(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Attribute):
            return self._resolve_path(node)
        if isinstance(node, ast.Name):
            return self._lookup_start_method_alias(node.id)
        return None

    def _bind_name(self, name: str) -> None:
        self.bound_scopes[-1].add(name)
        self.module_alias_scopes[-1].pop(name, None)
        self.call_alias_scopes[-1].pop(name, None)
        self.start_method_alias_scopes[-1].pop(name, None)

    def _temporarily_bind_name(
        self,
        index: int,
        name: str,
    ) -> Callable[[], None]:
        had_bound = name in self.bound_scopes[index]
        saved_module_alias = self.module_alias_scopes[index].pop(
            name,
            _MISSING,
        )
        saved_call_alias = self.call_alias_scopes[index].pop(name, _MISSING)
        saved_start_method_alias = self.start_method_alias_scopes[index].pop(
            name,
            _MISSING,
        )
        self.bound_scopes[index].add(name)

        def restore() -> None:
            if not had_bound:
                self.bound_scopes[index].discard(name)
            if saved_module_alias is not _MISSING:
                self.module_alias_scopes[index][name] = cast(
                    str,
                    saved_module_alias,
                )
            if saved_call_alias is not _MISSING:
                self.call_alias_scopes[index][name] = cast(
                    str,
                    saved_call_alias,
                )
            if saved_start_method_alias is not _MISSING:
                self.start_method_alias_scopes[index][name] = cast(
                    str, saved_start_method_alias
                )

        return restore

    def _class_binding_scope_index(self) -> int | None:
        index = len(self.scope_kinds) - 2
        if index < 0 or self.scope_kinds[index] == "class":
            return None
        return index

    def _lookup_module_alias(self, name: str) -> str | None:
        for index in range(len(self.module_alias_scopes) - 1, -1, -1):
            if self._scope_hidden_from_current_lookup(index):
                continue
            if name in self.module_alias_scopes[index]:
                return self.module_alias_scopes[index][name]
            if name in self.bound_scopes[index]:
                return None
        return name

    def _lookup_call_alias(self, name: str) -> str | None:
        for index in range(len(self.call_alias_scopes) - 1, -1, -1):
            if self._scope_hidden_from_current_lookup(index):
                continue
            if name in self.call_alias_scopes[index]:
                return self.call_alias_scopes[index][name]
            if name in self.bound_scopes[index]:
                return None
        return None

    def _lookup_start_method_alias(self, name: str) -> str | None:
        for index in range(
            len(self.start_method_alias_scopes) - 1,
            -1,
            -1,
        ):
            if self._scope_hidden_from_current_lookup(index):
                continue
            if name in self.start_method_alias_scopes[index]:
                return self.start_method_alias_scopes[index][name]
            if name in self.bound_scopes[index]:
                return None
        return None

    def _is_bound_name(self, name: str) -> bool:
        return any(
            name in scope
            for index, scope in reversed(list(enumerate(self.bound_scopes)))
            if not self._scope_hidden_from_current_lookup(index)
        )

    def _scope_hidden_from_current_lookup(self, index: int) -> bool:
        if self.scope_kinds[index] != "class":
            return False
        return any(
            kind == "function" for kind in self.scope_kinds[index + 1 :]
        )

    def _unsafe_attribute_call(self, func: ast.Attribute) -> str | None:
        full_path = self._resolve_path(func)
        if full_path is None:
            return None

        unsafe_call = self._unsafe_call_alias_for_path(full_path)
        if unsafe_call is not None:
            return f"{unsafe_call}()"

        return None

    def _unsafe_call_alias_for_path(self, full_path: str) -> str | None:
        for module, unsafe_attrs in UNSAFE_ATTR_CALLS.items():
            prefix = f"{module}."
            if not full_path.startswith(prefix):
                continue
            attr = full_path.removeprefix(prefix)
            if "." in attr:
                continue
            if attr in unsafe_attrs:
                return f"{module}.{attr}"

        for module, prefixes in UNSAFE_ATTR_PREFIXES.items():
            prefix = f"{module}."
            if not full_path.startswith(prefix):
                continue
            attr = full_path.removeprefix(prefix)
            if "." not in attr and any(attr.startswith(p) for p in prefixes):
                return f"{module}.{attr}"

        return None

    def _unsafe_start_method_call(
        self,
        node: ast.Call,
        call_path: str | None,
    ) -> str | None:
        if call_path not in UNSAFE_START_METHOD_CALLS:
            return None

        method = self._start_method_literal(node)
        if method is None or method == "spawn":
            return None

        return f"{call_path}({method!r})"

    def _start_method_literal(self, node: ast.Call) -> str | None:
        if node.args:
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(
                value.value, str
            ):
                return value.value

        for keyword in node.keywords:
            if keyword.arg != "method":
                continue
            value = keyword.value
            if isinstance(value, ast.Constant) and isinstance(
                value.value, str
            ):
                return value.value

        return None

    def _resolve_path(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return self._lookup_module_alias(node.id)
        if isinstance(node, ast.Call):
            return self._aliases_for_value(node).module
        if isinstance(node, ast.Attribute):
            value = self._resolve_path(node.value)
            if value is None:
                return None
            return f"{value}.{node.attr}"
        return None
