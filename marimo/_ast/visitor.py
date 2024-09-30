# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import itertools
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional, Union
from uuid import uuid4

from marimo import _loggers
from marimo._ast.sql_visitor import (
    find_from_targets,
    find_sql_defs,
    normalize_sql_f_string,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.variables import is_local

LOGGER = _loggers.marimo_logger()

Name = str

Language = Literal["python", "sql"]


@dataclass
class ImportData:
    # full module name
    # e.g., a.b.c.
    module: str
    # variable name
    definition: str
    # fully qualified import symbol:
    # import a.b => symbol == None
    # from a.b import c => symbol == a.b.c
    imported_symbol: Optional[str] = None
    import_level: Optional[int] = None

    def __post_init__(self) -> None:
        self.namespace = self.module.split(".")[0]


@dataclass
class VariableData:
    # "table", "view", and "schema" are SQL variables, not Python.
    kind: Literal[
        "function", "class", "import", "variable", "table", "view", "schema"
    ] = "variable"

    # If kind == function or class, it may be dependent on externally defined
    # variables.
    #
    # NB: This is populated by `ScopedVisitor.ref_stack`. Ref stack holds the
    # references required for the current context, it's more general than a
    # "block", since it covers all variable level interactions.
    # e.g.
    # >> x = foo + bar
    # x has the required refs foo and bar, and ref_stack holds that context
    # while traversing the tree.
    required_refs: set[Name] = field(default_factory=set)

    # For kind == import
    import_data: Optional[ImportData] = None

    @property
    def language(self) -> Language:
        return (
            "sql"
            if (
                self.kind == "table"
                or self.kind == "schema"
                or self.kind == "view"
            )
            else "python"
        )


@dataclass
class Block:
    """A scope in which names are declared."""

    # Defined names
    defs: set[Name] = field(default_factory=set)
    # Names defined with the global keyword
    global_names: set[Name] = field(default_factory=set)
    # Map from defined names to metadata about their variables
    variable_data: dict[Name, list[VariableData]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # Comprehensions have special scoping rules
    is_comprehension: bool = False

    def is_defined(self, name: str) -> bool:
        return any(name == defn for defn in self.defs)


@dataclass
class ObscuredScope:
    """The scope in which a name is hidden."""

    # Variable id if this block hides a name
    obscured: Optional[str] = None


@dataclass
class RefData:
    """Metadata about variables referenced but not defined by a cell."""

    # Whether the ref was deleted
    deleted: bool
    # Ancestors of the block in which this ref was used
    parent_blocks: list[Block]


NamedNode = Union[
    ast.Name,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.arg,
    ast.Global,
    "ast.MatchAs",  # type: ignore
    "ast.MatchMapping",  # type: ignore
    "ast.MatchStar",  # type: ignore
    "ast.TypeVar",  # type: ignore
    "ast.ParamSpec",  # type: ignore
    "ast.TypeVarTuple",  # type: ignore
]


class ScopedVisitor(ast.NodeVisitor):
    def __init__(
        self,
        mangle_prefix: Optional[str] = None,
        ignore_local: bool = False,
        on_def: Callable[[NamedNode, str, list[Block]], None] | None = None,
        on_ref: Callable[[NamedNode], None] | None = None,
    ) -> None:
        self.block_stack: list[Block] = [Block()]
        # Names to be loaded into a variable required_refs
        self.ref_stack: list[set[Name]] = [set()]
        self.obscured_scope_stack: list[ObscuredScope] = []
        # Mapping from referenced names to their metadata
        self._refs: dict[Name, RefData] = {}
        # Function (node, name, block stack) -> None
        self._on_def = on_def if on_def is not None else lambda *_: None
        # Function (node) -> None
        self._on_ref = on_ref if on_ref is not None else lambda *_: None
        # Unique prefix used to mangle cell-local variable names
        self.id = (
            str(uuid4()).replace("-", "_")
            if mangle_prefix is None
            else mangle_prefix
        )
        self.is_local = (lambda _: False) if ignore_local else is_local
        self.language: Language = "python"

    @property
    def defs(self) -> set[Name]:
        """Get all global defs."""
        return self.block_stack[0].defs

    @property
    def variable_data(self) -> dict[Name, list[VariableData]]:
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
        if self.is_local(name) and (
            len(self.block_stack) == 1 or ignore_scope
        ):
            return f"_{self.id}{name}"
        else:
            return name

    def _get_alias_name(self, node: ast.alias) -> str:
        """Get the string name of an imported alias.

        Mangles the "as" name if it's a local variable.

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
            node.asname = self._if_local_then_mangle(node.asname)
            return node.asname

    def _is_defined(self, identifier: str) -> bool:
        """Check if `identifier` is defined in any block."""
        return any(block.is_defined(identifier) for block in self.block_stack)

    def _add_ref(
        self, node: NamedNode | None, name: Name, deleted: bool
    ) -> None:
        """Register a referenced name."""
        self._refs[name] = RefData(
            deleted=deleted,
            parent_blocks=self.block_stack[:-1],
        )
        self.ref_stack[-1].add(name)
        if node is not None:
            self._on_ref(node)

    def _remove_ref(self, name: Name) -> None:
        """Remove a referenced name."""
        del self._refs[name]

    def _define_in_block(
        self, name: Name, variable_data: VariableData, block_idx: int
    ) -> None:
        """Define a name in a given block."""

        self.block_stack[block_idx].defs.add(name)
        self.block_stack[block_idx].variable_data[name].append(variable_data)
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

    def _define(
        self, node: NamedNode | None, name: Name, variable_data: VariableData
    ) -> None:
        """Define a name in the current block.

        Names created with the global keyword are added to the top-level
        (global scope) block.
        """
        block_idx = 0 if name in self.block_stack[-1].global_names else -1
        self._define_in_block(name, variable_data, block_idx=block_idx)
        if node is not None:
            self._on_def(node, name, self.block_stack)

    def _push_block(self, is_comprehension: bool) -> None:
        """Push a block onto the block stack."""
        self.block_stack.append(Block(is_comprehension=is_comprehension))

    def _pop_block(self) -> None:
        """Pop a block from the block stack."""
        self.block_stack.pop()

    def _push_obscured_scope(self, obscured: Optional[str]) -> None:
        """Push scope onto the stack."""
        self.obscured_scope_stack.append(ObscuredScope(obscured=obscured))

    def _pop_obscured_scope(self) -> None:
        """Pop scope from the stack."""
        self.obscured_scope_stack.pop()

    def generic_visit(self, node: ast.AST) -> ast.AST:
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
        elif isinstance(node, ast.Try) or (
            sys.version_info >= (3, 11) and isinstance(node, ast.TryStar)
        ):
            if sys.version_info < (3, 11):
                assert isinstance(node, ast.Try)
            # "Try" nodes have "handlers" that introduce exception context
            # variables that are tied to the try block, and don't exist beyond
            # it.
            for stmt in node.body:
                self.visit(stmt)
            for handler in node.handlers:
                self._push_obscured_scope(obscured=handler.name)
                self.visit(handler)
                self._pop_obscured_scope()
            for stmt in node.orelse:
                self.visit(stmt)
            for stmt in node.finalbody:
                self.visit(stmt)
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
        return node

    def _visit_and_get_refs(self, node: ast.AST) -> set[Name]:
        """Create a ref scope for the variable to be declared (e.g. function,
        class), visit the children the node, propagate the refs to the higher
        scope and then return the refs."""
        self.ref_stack.append(set())
        self.generic_visit(node)
        refs = self.ref_stack.pop()
        # The scope a level up from the one just investigated also is dependent
        # on these refs. Consider the case:
        # >> def foo():
        # >>   def bar(): <- current scope
        # >>     print(x)
        #
        # the variable `foo` needs to be aware that it may require the ref `x`
        # during execution.
        self.ref_stack[-1].update(refs)
        return refs

    # ClassDef and FunctionDef nodes don't have ast.Name nodes as children
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = self._if_local_then_mangle(node.name)
        refs = self._visit_and_get_refs(node)
        self._define(
            node,
            node.name,
            VariableData(kind="class", required_refs=refs),
        )
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        node.name = self._if_local_then_mangle(node.name)
        refs = self._visit_and_get_refs(node)
        self._define(
            node,
            node.name,
            VariableData(kind="function", required_refs=refs),
        )
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = self._if_local_then_mangle(node.name)
        refs = self._visit_and_get_refs(node)
        self._define(
            node,
            node.name,
            VariableData(kind="function", required_refs=refs),
        )
        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        # If the call name is sql and has one argument, and the argument is
        # a string literal, then it's likely to be a SQL query.
        # It must also come from the `mo` or `duckdb` module.
        #
        # This check is brittle, since we can't detect at parse time whether
        # 'mo'/'marimo' actually refer to the marimo library, but it gets
        # the job done.
        valid_sql_calls = [
            "marimo.sql",
            "mo.sql",
            "duckdb.execute",
            "duckdb.sql",
        ]
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and f"{node.func.value.id}.{node.func.attr}" in valid_sql_calls
            and len(node.args) == 1
        ):
            self.language = "sql"
            first_arg = node.args[0]
            sql: Optional[str] = None
            if isinstance(first_arg, ast.Constant):
                sql = first_arg.s
            elif isinstance(first_arg, ast.JoinedStr):
                sql = normalize_sql_f_string(first_arg)

            if (
                isinstance(sql, str)
                and DependencyManager.duckdb.has_at_version(
                    min_version="1.0.0"
                )
                and sql
            ):
                import duckdb  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

                # Add all tables in the query to the ref scope
                try:
                    # TODO: This function raises a CatalogError on CREATE VIEW
                    # statements that reference tables that are not yet
                    # defined, such
                    #
                    # as CREATE OR REPLACE VIEW my_view as SELECT * from my_df
                    #
                    # This breaks dependency parsing.
                    statements = duckdb.extract_statements(sql)
                except duckdb.ProgrammingError:
                    # The user's sql query may have a syntax error,
                    # or duckdb failed for an unknown reason; don't
                    # break marimo.
                    self.generic_visit(node)
                    return node
                except BaseException as e:
                    # We catch base exceptions because we don't want to
                    # fail due to bugs in duckdb -- users code should
                    # be saveable no matter what
                    LOGGER.warning("Unexpected duckdb error %s", e)
                    self.generic_visit(node)
                    return node

                for statement in statements:
                    # Parse the refs and defs of each statement
                    try:
                        tables = duckdb.get_table_names(statement.query)
                        # TODO(akshayka): more comprehensive parsing
                        # of the statement -- schemas can show up in
                        # joins, queries, ...
                        from_targets = find_from_targets(statement.query)
                    except duckdb.ProgrammingError:
                        self.generic_visit(node)
                        continue
                    except BaseException as e:
                        LOGGER.warning("Unexpected duckdb error %s", e)
                        self.generic_visit(node)
                        continue

                    for name in itertools.chain(tables, from_targets):
                        # Name (table, db) may be a URL or something else that
                        # isn't a Python variable
                        if name.isidentifier():
                            self._add_ref(None, name, deleted=False)

                    # Add all tables/dbs created in the query to the defs
                    try:
                        sql_defs = find_sql_defs(sql)
                    except duckdb.ProgrammingError:
                        self.generic_visit(node)
                        continue
                    except BaseException as e:
                        LOGGER.warning("Unexpected duckdb error %s", e)
                        self.generic_visit(node)
                        continue

                    for _table in sql_defs.tables:
                        self._define(None, _table, VariableData("table"))
                    for _view in sql_defs.views:
                        self._define(None, _view, VariableData("view"))
                    for _schema in sql_defs.schemas:
                        self._define(None, _schema, VariableData("schema"))

        # Visit arguments, keyword args, etc.
        self.generic_visit(node)
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        # Inject the dummy name `_lambda` into ref scope to denote there's a
        # callable that might require additional refs.
        self.ref_stack[-1].add("_lambda")
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._if_local_then_mangle(node.arg)
        self._define(node, node.arg, VariableData(kind="variable"))
        if node.annotation is not None:
            self.visit(node.annotation)
        return node

    def visit_arguments(self, node: ast.arguments) -> ast.arguments:
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
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        # Visit the value first, to handle cases like
        #
        # class A:
        #   x = x
        #
        # Handling value first is required to register `x` as a ref.
        self.ref_stack.append(set())
        self.visit(node.value)
        for target in node.targets:
            self.visit(target)
        refs = self.ref_stack.pop()
        self.ref_stack[-1].update(refs)
        return node

    def visit_AugAssign(self, node: ast.AugAssign) -> ast.AugAssign:
        # Augmented assign (has op)
        # e.g., x += 1
        self.ref_stack.append(set())
        self.visit(node.value)
        self.visit(node.target)
        refs = self.ref_stack.pop()
        self.ref_stack[-1].update(refs)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        # Annotated assign
        # e.g., x: int = 0
        self.ref_stack.append(set())
        if node.value is not None:
            self.visit(node.value)
        self.visit(node.annotation)
        self.visit(node.target)
        refs = self.ref_stack.pop()
        self.ref_stack[-1].update(refs)
        return node

    def visit_comprehension(
        self, node: ast.comprehension
    ) -> ast.comprehension:
        # process potential refs before defs, to handle patterns like
        #
        # [ ... for x in x]
        #
        # In defining scoping, Python parses iter first, then target, then ifs
        self.visit(node.iter)
        self.visit(node.target)
        for _if in node.ifs:
            self.visit(_if)
        return node

    def visit_NamedExpr(self, node: ast.NamedExpr) -> ast.NamedExpr:
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
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
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
        #
        # NB: Nodes like "Try" nodes introduce variable names that do not exist
        # beyond their inner scope. We traverse blocks to see if the name is
        # "obscured" in this way.

        for scope in self.obscured_scope_stack:
            if node.id == scope.obscured:
                self.generic_visit(node)
                return node

        if isinstance(node.ctx, ast.Store):
            node.id = self._if_local_then_mangle(node.id)
            self._define(
                node,
                node.id,
                VariableData(
                    kind="variable", required_refs=self.ref_stack[-1]
                ),
            )
        elif (
            isinstance(node.ctx, ast.Load)
            and not self._is_defined(node.id)
            and not self.is_local(node.id)
        ):
            self._add_ref(node, node.id, deleted=False)
        elif (
            isinstance(node.ctx, ast.Del)
            and not self._is_defined(node.id)
            and not self.is_local(node.id)
        ):
            self._add_ref(node, node.id, deleted=True)
        elif self.is_local(node.id):
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
        else:
            # Not a reference; ast.Load, ast.Del on a variable that's already
            # defined; invoke the callback
            if node is not None:
                self._on_def(node, node.id, self.block_stack)

        # Handle refs on the block scope level, or capture cell level
        # references.
        if (
            isinstance(node.ctx, ast.Load)
            and self._is_defined(node.id)
            and node.id not in self.ref_stack[-1]
            and (
                node.id not in self.block_stack[-1].defs
                or len(self.block_stack) == 1
            )
        ):
            self.ref_stack[-1].add(node.id)

        self.generic_visit(node)
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:
        node.names = [
            self._if_local_then_mangle(name, ignore_scope=True)
            for name in node.names
        ]
        for name in node.names:
            self.block_stack[-1].global_names.add(name)
            self._add_ref(node, name, deleted=False)
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias_node in node.names:
            variable_name = self._get_alias_name(alias_node)
            self._define(
                None,
                variable_name,
                VariableData(
                    kind="import",
                    import_data=ImportData(
                        module=alias_node.name,
                        definition=variable_name,
                        imported_symbol=None,
                    ),
                ),
            )
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        module = node.module if node.module is not None else ""
        # we don't recurse into the alias nodes, since we define the
        # aliases here
        for alias_node in node.names:
            variable_name = self._get_alias_name(alias_node)
            original_name = alias_node.name
            self._define(
                None,
                variable_name,
                VariableData(
                    kind="import",
                    import_data=ImportData(
                        module=module,
                        definition=variable_name,
                        imported_symbol=module + "." + original_name,
                        import_level=node.level,
                    ),
                ),
            )
        return node

    if sys.version_info >= (3, 10):
        # Match statements were introduced in Python 3.10
        #
        # Top-level match statements are awkward in marimo --- at parse-time,
        # we have to register all names in every case/pattern as globals (since
        # we don't know the value of the match subject), even though only a
        # subset of the names will be bound at runtime. For this reason, in
        # marimo, match statements should really only be used in local scopes.
        def visit_MatchAs(self, node: ast.MatchAs) -> ast.MatchAs:
            if node.name is not None:
                node.name = self._if_local_then_mangle(node.name)
                self._define(
                    node,
                    node.name,
                    VariableData(kind="variable"),
                )
            if node.pattern is not None:
                # pattern may contain additional MatchAs statements in it
                self.visit(node.pattern)
            return node

        def visit_MatchMapping(
            self, node: ast.MatchMapping
        ) -> ast.MatchMapping:
            if node.rest is not None:
                node.rest = self._if_local_then_mangle(node.rest)
                self._define(
                    node,
                    node.rest,
                    VariableData(kind="variable"),
                )
            for key in node.keys:
                self.visit(key)
            for pattern in node.patterns:
                self.visit(pattern)
            return node

        def visit_MatchStar(self, node: ast.MatchStar) -> ast.MatchStar:
            if node.name is not None:
                node.name = self._if_local_then_mangle(node.name)
                self._define(
                    node,
                    node.name,
                    VariableData(kind="variable"),
                )
            return node

    if sys.version_info >= (3, 12):

        def visit_TypeVar(self, node: ast.TypeVar) -> ast.TypeVar:
            # node.name is a str, not an ast.Name node
            self._define(
                node,
                node.name,
                VariableData(
                    kind="variable", required_refs=self.ref_stack[-1]
                ),
            )
            if isinstance(node.bound, tuple):
                for name in node.bound:
                    self.visit(name)
            elif node.bound is not None:
                self.visit(node.bound)
            return node

        def visit_ParamSpec(self, node: ast.ParamSpec) -> ast.ParamSpec:
            # node.name is a str, not an ast.Name node
            self._define(
                node,
                node.name,
                VariableData(
                    kind="variable", required_refs=self.ref_stack[-1]
                ),
            )
            return node

        def visit_TypeVarTuple(
            self, node: ast.TypeVarTuple
        ) -> ast.TypeVarTuple:
            # node.name is a str, not an ast.Name node
            self._define(
                node,
                node.name,
                VariableData(
                    kind="variable", required_refs=self.ref_stack[-1]
                ),
            )
            return node
