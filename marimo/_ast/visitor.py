# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from typing import Literal, Optional
from uuid import uuid4

Name = str


@dataclass
class ImportData:
    # full module name
    # e.g., a.b.c.
    module: str
    # fully qualified import symbol:
    # import a.b => symbol == None
    # from a.b import c => symbol == a.b.c
    imported_symbol: Optional[str] = None
    import_level: Optional[int] = None

    def __post_init__(self) -> None:
        self.namespace = self.module.split(".")[0]


@dataclass
class VariableData:
    kind: Literal["function", "class", "import", "variable"] = "variable"

    # For kind == import
    import_data: Optional[ImportData] = None


def is_local(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


@dataclass
class Block:
    """A scope in which names are declared."""

    # Defined names
    defs: set[Name] = field(default_factory=set)
    # Names defined with the global keyword
    global_names: set[Name] = field(default_factory=set)
    # Map from defined names to metadata about their variables
    variable_data: dict[Name, VariableData] = field(default_factory=dict)
    # Comprehensions have special scoping rules
    is_comprehension: bool = False

    def is_defined(self, name: str) -> bool:
        return any(name == defn for defn in self.defs)


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
    def defs(self) -> set[Name]:
        """Get all global defs."""
        return self.block_stack[0].defs

    @property
    def variable_data(self) -> dict[Name, VariableData]:
        """Get data accompanying globals."""
        return self.block_stack[0].variable_data

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
        if is_local(name) and (len(self.block_stack) == 1 or ignore_scope):
            return f"_{self.id}{name}"
        else:
            return name

    def _get_alias_name(self, node: ast.alias) -> str:
        """Get the string name of an imported alias

        NB: We disallow `import *` because Python only allows
        star imports at module-level, but we store cells as functions.
        """
        if node.asname is None:
            # Imported name without an "as" clause. Examples:
            #   import [a.b.c] - we define a
            #   from foo import [a] - we define a
            #   from foo import [*] - we don't define anything
            #
            # Note:
            # Don't mangle - user has no control over package name
            basename = node.name.split(".")[0]
            if basename == "*":
                line = (
                    f"line {node.lineno}"
                    if hasattr(node, "lineno")
                    else "line ..."
                )
                raise SyntaxError(
                    f"{line} SyntaxError: `import *` is not allowed in marimo."
                )
            return basename
        else:
            return self._if_local_then_mangle(node.asname)

    def _is_defined(self, identifier: str) -> bool:
        """Check if `identifier` is defined in any block."""
        return any(block.is_defined(identifier) for block in self.block_stack)

    def _add_ref(self, name: Name, deleted: bool) -> None:
        """Register a referenced name."""
        self._refs[name] = RefData(
            deleted=deleted,
            parent_blocks=self.block_stack[:-1],
        )

    def _remove_ref(self, name: Name) -> None:
        """Remove a referenced name."""
        del self._refs[name]

    def _define_in_block(
        self, name: Name, variable_data: VariableData, block_idx: int
    ) -> None:
        """Define a name in a given block."""

        self.block_stack[block_idx].defs.add(name)
        self.block_stack[block_idx].variable_data[name] = variable_data
        # If `name` is added to the top-level block, it is also evicted from
        # any captured refs (if present) --- this handles cases where a name is
        # encountered and captured before it is declared, such as in
        #
        # ```
        # def f():
        #   print(x)
        # x = 0
        # ```
        if (
            name in self._refs
            and self.block_stack[block_idx] in self._refs[name].parent_blocks
        ):
            # `name` was used as a capture, not a reference
            self._remove_ref(name)

    def _define(self, name: Name, variable_data: VariableData) -> None:
        """Define a name in the current block.

        Names created with the global keyword are added to the top-level
        (global scope) block.
        """
        block_idx = 0 if name in self.block_stack[-1].global_names else -1
        self._define_in_block(name, variable_data, block_idx=block_idx)

    def _push_block(self, is_comprehension: bool) -> None:
        """Push a block onto the block stack."""
        self.block_stack.append(Block(is_comprehension=is_comprehension))

    def _pop_block(self) -> None:
        """Pop a block from the block stack."""
        self.block_stack.pop()

    def generic_visit(self, node: ast.AST) -> None:
        """Visits the children of node and manages the block stack.

        Note: visit calls visit_ClassName, or generic_visit() if the former
        doesn't exist. That means that _this method should never call
        visit on `node`_, as this could lead to unbounded recursion.
        (Calling visit on `node`'s children is fine.) In summary:
        call super().generic_visit on `node` and `visit()` on node's children.
        """
        if isinstance(node, (ast.ClassDef, ast.Lambda)):
            # These AST nodes introduce a new scope, but otherwise do not
            # require special treatment.
            self._push_block(is_comprehension=False)
            super().generic_visit(node)
            self._pop_block()
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            self._push_block(is_comprehension=False)
            if sys.version_info >= (3, 12):
                # We need to visit generic type parameters before arguments
                # to make sure type parameters don't get added as refs. eg, in
                #
                #   def foo[U](u: U) -> U: ...
                #
                # `U` should not be a ref
                for child in node.type_params:
                    self.visit(child)
            # This will revisit the type_params, but that's okay because
            # visiting is idempotent
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
        elif sys.version_info >= (3, 12) and isinstance(node, ast.TypeAlias):
            self.visit(node.name)
            self._push_block(is_comprehension=False)
            for t in node.type_params:
                self.visit(t)
            self.visit(node.value)
            self._pop_block()
        else:
            # Other nodes that don't introduce a new scope
            super().generic_visit(node)

    # ClassDef and FunctionDef nodes don't have ast.Name nodes as children
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(node.name, VariableData(kind="class"))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(node.name, VariableData(kind="function"))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        node.name = self._if_local_then_mangle(node.name)
        self._define(node.name, VariableData(kind="function"))
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        node.arg = self._if_local_then_mangle(node.arg)
        self._define(node.arg, VariableData(kind="variable"))
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
            for block_idx, block in reversed(
                list(enumerate(self.block_stack))
            ):
                # go up the block stack until we find the first
                # non-comprehension block
                if not block.is_comprehension:
                    node.target.id = self._if_local_then_mangle(
                        node.target.id,
                        ignore_scope=(block == self.block_stack[0]),
                    )
                    self._define_in_block(
                        node.target.id,
                        VariableData(kind="variable"),
                        block_idx=block_idx,
                    )
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
            self._define(node.id, VariableData(kind="variable"))
        elif (
            isinstance(node.ctx, ast.Load)
            and not self._is_defined(node.id)
            and not is_local(node.id)
        ):
            self._add_ref(node.id, deleted=False)
        elif (
            isinstance(node.ctx, ast.Del)
            and not self._is_defined(node.id)
            and not is_local(node.id)
        ):
            self._add_ref(node.id, deleted=True)
        elif is_local(node.id):
            mangled_name = self._if_local_then_mangle(
                node.id, ignore_scope=True
            )
            for block in reversed(self.block_stack):
                if block == self.block_stack[0] and block.is_defined(
                    mangled_name
                ):
                    node.id = mangled_name
                elif block.is_defined(node.id):
                    break

        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        node.names = [
            self._if_local_then_mangle(name, ignore_scope=True)
            for name in node.names
        ]
        for name in node.names:
            self.block_stack[-1].global_names.add(name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias_node in node.names:
            variable_name = self._get_alias_name(alias_node)
            self._define(
                variable_name,
                VariableData(
                    kind="import",
                    import_data=ImportData(
                        module=alias_node.name, imported_symbol=None
                    ),
                ),
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module if node.module is not None else ""
        # we don't recurse into the alias nodes, since we define the
        # aliases here
        for alias_node in node.names:
            variable_name = self._get_alias_name(alias_node)
            original_name = alias_node.name
            self._define(
                variable_name,
                VariableData(
                    kind="import",
                    import_data=ImportData(
                        module=module,
                        imported_symbol=module + "." + original_name,
                        import_level=node.level,
                    ),
                ),
            )

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
                self._define(node.name, VariableData(kind="variable"))
            if node.pattern is not None:
                # pattern may contain additional MatchAs statements in it
                self.visit(node.pattern)

        def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
            if node.rest is not None:
                node.rest = self._if_local_then_mangle(node.rest)
                self._define(node.rest, VariableData(kind="variable"))
            for key in node.keys:
                self.visit(key)
            for pattern in node.patterns:
                self.visit(pattern)

        def visit_MatchStar(self, node: ast.MatchStar) -> None:
            if node.name is not None:
                node.name = self._if_local_then_mangle(node.name)
                self._define(node.name, VariableData(kind="variable"))

    if sys.version_info >= (3, 12):

        def visit_TypeVar(self, node: ast.TypeVar) -> None:
            # node.name is a str, not an ast.Name node
            self._define(node.name, VariableData(kind="variable"))
            if isinstance(node.bound, tuple):
                for name in node.bound:
                    self.visit(name)
            elif node.bound is not None:
                self.visit(node.bound)

        def visit_ParamSpec(self, node: ast.ParamSpec) -> None:
            # node.name is a str, not an ast.Name node
            self._define(node.name, VariableData(kind="variable"))

        def visit_TypeVarTuple(self, node: ast.TypeVarTuple) -> None:
            # node.name is a str, not an ast.Name node
            self._define(node.name, VariableData(kind="variable"))
