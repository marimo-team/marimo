# Copyright 2026 Marimo. All rights reserved.
"""Infer parameter annotations for generated cell signatures.

marimo joins the cells into one module in dependency order and asks a
backend for the type of every definition of each candidate variable. The
module-level names of the generated file are setup cell definitions and
top-level functions or classes. marimo keeps a type only when every name in
it is available before every consuming signature. A library class is
spelled through the setup cell, as `np.ndarray` or `Path`, and the backend
must confirm that the spelling names the same class. Every other type is
dropped. Nothing is quoted.
"""

from __future__ import annotations

import ast
import warnings
from collections import defaultdict
from dataclasses import dataclass
from heapq import heapify, heappop, heappush
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from marimo import _loggers
from marimo._ast.variables import BUILTINS
from marimo._ast.visitor import AnnotationData, Name, ScopedVisitor
from marimo._utils.strings import standardize_annotation_quotes

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.toplevel import TopLevelExtraction, TopLevelStatus

LOGGER = _loggers.marimo_logger()

TypeInferenceMode = Literal["off", "jedi"]

# A fixed-length tuple longer than this is written as `tuple[T, ...]`.
MAX_TUPLE_ELEMENTS = 3

# A union with more members than this says little about the value. Such a
# type is dropped rather than written.
MAX_UNION_MEMBERS = 3

# Types that admit every value. An annotation naming one is dropped.
_BROAD_TYPES = frozenset({"object", "Any"})

# Used when no formatting config is available.
DEFAULT_LINE_LENGTH = 79

# What a parameter line costs besides its name and annotation: the indent,
# the `: ` separator, and the trailing comma.
_PARAMETER_OVERHEAD = len("    ") + len(": ") + len(",")

# The synthesized module is never written to disk. The stem is what jedi
# reports as the module of a class the notebook defines.
PROBE_MODULE_NAME = "__marimo_probe__"

_BUILTINS = "builtins"

# `typing` spellings that jedi uses in type hints, and the builtin each one
# is written as in a signature.
_TYPING_TO_BUILTIN = {
    "List": "list",
    "Dict": "dict",
    "Tuple": "tuple",
    "Set": "set",
    "FrozenSet": "frozenset",
    "Type": "type",
}


@dataclass(frozen=True)
class Inferred:
    """One value a backend inferred for a definition."""

    # Dotted path of the value's class, such as `pandas.core.frame.DataFrame`.
    full_name: str
    # `instance`, `class`, `function`, or `module`.
    kind: str
    # The backend's spelling of the type with generic parameters, if any.
    hint: str | None = None


class Backend(Protocol):
    def infer_definitions(
        self, source: str, names: set[Name], search_path: Path | None
    ) -> dict[Name, list[Inferred]]:
        """Infer every module-level definition of each name in `source`.

        A name is left out when any of its definitions cannot be inferred.
        """
        ...

    def resolve(
        self, source: str, expressions: list[str], search_path: Path | None
    ) -> list[Inferred | None]:
        """What each expression names when evaluated after `source`."""
        ...


def infer_annotations(
    extraction: TopLevelExtraction,
    setup_cell: CellImpl | None,
    *,
    filename: str | None,
    mode: TypeInferenceMode,
    line_length: int = DEFAULT_LINE_LENGTH,
    backend: Backend | None = None,
) -> dict[Name, AnnotationData]:
    """Infer annotations for the variables that cells read as parameters.

    Returns only annotations that the generated file can spell bare and
    that fit on one parameter line within `line_length`.
    """
    if mode == "off":
        return {}
    names = candidate_names(extraction)
    if not names:
        return {}
    if backend is None:
        backend = JediBackend()

    source = probe_module(extraction, setup_cell)
    search_path = Path(filename).parent if filename else None
    inferred = backend.infer_definitions(source, names, search_path)
    if not inferred:
        return {}

    spellings = _ClassSpellings(
        extraction, setup_cell, backend, source, search_path
    )
    # NB. `unshadowed` only accounts for cell definitions. A setup cell that
    # rebinds `int` makes the bare name mean something else in the file.
    setup_defs = set(setup_cell.defs) if setup_cell is not None else set()
    scope = _Scope(
        allowed_refs=extraction.allowed_refs,
        builtins=extraction.unshadowed - setup_defs,
    )
    annotations: dict[Name, AnnotationData] = {}
    for name in sorted(inferred):
        node = _declared_type(inferred[name], scope, spellings)
        if node is None:
            continue
        annotation = _annotation(node)
        # NB. A type too long for its own line is dropped, not wrapped.
        budget = line_length - len(name) - _PARAMETER_OVERHEAD
        if len(annotation.repr) > budget:
            continue
        annotations[name] = annotation

    # Signatures are evaluated in file order, not dependency order. Keep
    # one annotation per variable only if every consuming signature can
    # evaluate it before the notebook runs.
    available = scope.builtins | setup_defs
    for status in extraction:
        if status.is_toplevel:
            available.update(status.defs)
        elif status.is_cell:
            for name in (status.refs - status.defs) & annotations.keys():
                if annotations[name].refs - available:
                    del annotations[name]
    return annotations


@dataclass(frozen=True)
class _Scope:
    """Names an annotation in the generated file can use."""

    # Every name in scope at module level.
    allowed_refs: set[Name]
    # Builtin classes that nothing in the notebook rebinds.
    builtins: set[Name]


def candidate_names(extraction: TopLevelExtraction) -> set[Name]:
    """Variables worth probing: public, unannotated, and read by some cell."""
    variables = extraction.variables
    names: set[Name] = set()
    for status in extraction:
        if status.is_unparsable:
            continue
        for name in status.defs:
            data = variables.get(name)
            # Private names are filtered out of variable data at compile time.
            if data is None:
                continue
            if data.annotation_data is not None or data.language == "sql":
                continue
            # Module-scope names are never parameters, and names nothing
            # reads never appear in a signature.
            if name in extraction.allowed_refs:
                continue
            if name not in extraction.used_refs:
                continue
            names.add(name)
    return names


def module_aliases(setup_cell: CellImpl | None) -> dict[Name, str]:
    """Names the setup cell binds to whole modules, `np` to `numpy`.

    `from a import b` binds an object, not a module, and is left out.
    """
    if setup_cell is None:
        return {}
    aliases: dict[Name, str] = {}
    for name, entries in setup_cell.variable_data.items():
        import_data = entries[0].import_data
        if import_data is not None and import_data.imported_symbol is None:
            aliases[name] = import_data.module
    return aliases


def probe_module(
    extraction: TopLevelExtraction, setup_cell: CellImpl | None
) -> str:
    """The setup cell, then every cell in dependency order, as one module."""
    blocks: list[str] = []
    if setup_cell is not None and setup_cell.code.strip():
        blocks.append(setup_cell.code)
    for status in _dependency_order(extraction):
        tree = ast.parse(status.code)
        ScopedVisitor("cell_" + status.cell_id).visit(tree)
        blocks.append(ast.unparse(tree))
    body = "\n".join(blocks)
    if body and not body.endswith("\n"):
        body += "\n"
    return body


def _dependency_order(extraction: TopLevelExtraction) -> list[TopLevelStatus]:
    """Order cells so that each definition precedes its uses.

    File order breaks ties. Cells in a cycle keep their file order after
    every acyclic cell.
    """
    statuses = [status for status in extraction if not status.is_unparsable]
    position = {id(status): idx for idx, status in enumerate(statuses)}

    definer: dict[Name, TopLevelStatus] = {}
    for status in statuses:
        for name in status.defs:
            definer.setdefault(name, status)

    children: dict[int, list[TopLevelStatus]] = defaultdict(list)
    in_degree = {id(status): 0 for status in statuses}
    for status in statuses:
        parents = {
            id(definer[ref]): definer[ref]
            for ref in status.refs
            if ref in definer and definer[ref] is not status
        }
        in_degree[id(status)] = len(parents)
        for parent in parents.values():
            children[id(parent)].append(status)

    heap = [
        (position[id(status)], status)
        for status in statuses
        if in_degree[id(status)] == 0
    ]
    heapify(heap)
    ordered: list[TopLevelStatus] = []
    while heap:
        _, status = heappop(heap)
        ordered.append(status)
        for child in children[id(status)]:
            in_degree[id(child)] -= 1
            if in_degree[id(child)] == 0:
                heappush(heap, (position[id(child)], child))

    if len(ordered) < len(statuses):
        emitted = {id(status) for status in ordered}
        ordered.extend(s for s in statuses if id(s) not in emitted)
    return ordered


def definition_sites(
    source: str, names: set[Name]
) -> dict[Name, list[tuple[int, int]]]:
    """Line and column of every module-level binding of each name.

    Names with bindings that cannot be fully inferred are omitted, even
    when they also have ordinary assignments.
    """
    sites: dict[Name, list[tuple[int, int]]] = defaultdict(list)
    unsupported: set[Name] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            unsupported.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            unsupported.update(
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
            )
        elif isinstance(node, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)):
            if node.name is not None:
                unsupported.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest is not None:
            unsupported.add(node.rest)
        elif isinstance(
            node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            # Assignment expressions in comprehensions bind in the enclosing
            # scope, but their value is not inferred here.
            unsupported.update(
                child.target.id
                for child in ast.walk(node)
                if isinstance(child, ast.NamedExpr)
                and isinstance(child.target, ast.Name)
            )
        if isinstance(node, _SCOPES):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in names:
                sites[node.id].append((node.lineno, node.col_offset))
        for child in ast.iter_child_nodes(node):
            visit(child)

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    visit(tree)
    return {
        name: positions
        for name, positions in sites.items()
        if name not in unsupported
    }


_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


class JediBackend:
    """Static inference with jedi against the running interpreter."""

    def infer_definitions(
        self, source: str, names: set[Name], search_path: Path | None
    ) -> dict[Name, list[Inferred]]:
        sites = definition_sites(source, names)
        if not sites:
            return {}
        script = self._script(source, search_path)
        if script is None:
            return {}
        inferred: dict[Name, list[Inferred]] = {}
        for name, positions in sites.items():
            values: list[Inferred] = []
            for line, column in positions:
                found = self._infer(script, line, column)
                if not found:
                    break
                values.extend(found)
            else:
                inferred[name] = values
        return inferred

    def resolve(
        self, source: str, expressions: list[str], search_path: Path | None
    ) -> list[Inferred | None]:
        if not expressions:
            return []
        first_line = source.count("\n") + 1
        script = self._script(
            source + "\n".join(expressions) + "\n", search_path
        )
        if script is None:
            return [None] * len(expressions)
        resolved: list[Inferred | None] = []
        for offset, expression in enumerate(expressions):
            found = self._infer(script, first_line + offset, len(expression))
            resolved.append(found[0] if found else None)
        return resolved

    @staticmethod
    def _script(source: str, search_path: Path | None) -> object | None:
        # NB. jedi is a core dependency, but importing it costs a few hundred
        # milliseconds. Import it only when a save needs it.
        import jedi  # type: ignore

        script: object
        try:
            if search_path is None:
                script = jedi.Script(source)
            else:
                script = jedi.Script(
                    source,
                    path=str(search_path / f"{PROBE_MODULE_NAME}.py"),
                    project=jedi.Project(str(search_path)),
                )
            return script
        except Exception as e:
            LOGGER.debug("jedi could not load the notebook: %s", e)
            return None

    @staticmethod
    def _infer(script: object, line: int, column: int) -> list[Inferred]:
        values: list[Inferred] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                found = cast("list[object]", script.infer(line, column))  # type: ignore[attr-defined]
            except Exception as e:
                LOGGER.debug(
                    "jedi inference failed at %s:%s: %s", line, column, e
                )
                return []
            for definition in found:
                full_name = getattr(definition, "full_name", None)
                if not full_name:
                    continue
                # NB. jedi cannot spell every type it infers. A failed hint
                # still leaves the bare class from `full_name`.
                try:
                    hint = cast("str | None", definition.get_type_hint())  # type: ignore[attr-defined]
                except Exception:
                    hint = None
                values.append(
                    Inferred(
                        full_name=full_name,
                        kind=cast(str, getattr(definition, "type", "")),
                        hint=hint,
                    )
                )
        return values


class _ClassSpellings:
    """Spell a non-builtin class through names the setup cell puts in scope.

    The bare class name is a candidate when it is a module-level name of the
    generated file. Each setup cell module alias adds `alias.ClassName` when
    its module contains the class. The backend must confirm that a candidate
    names the inferred class.
    """

    def __init__(
        self,
        extraction: TopLevelExtraction,
        setup_cell: CellImpl | None,
        backend: Backend,
        source: str,
        search_path: Path | None,
    ) -> None:
        self._allowed = extraction.allowed_refs
        self._aliases = module_aliases(setup_cell)
        self._backend = backend
        self._source = source
        self._search_path = search_path
        self._cache: dict[str, ast.expr | None] = {}

    def spell(self, full_name: str) -> ast.expr | None:
        if full_name in self._cache:
            return self._cache[full_name]
        spelling = self._spell(full_name)
        self._cache[full_name] = spelling
        return spelling

    def _spell(self, full_name: str) -> ast.expr | None:
        module, _, class_name = full_name.rpartition(".")
        candidates: list[str] = []
        if class_name in self._allowed:
            candidates.append(class_name)
        for alias, alias_module in sorted(self._aliases.items()):
            if module == alias_module or module.startswith(alias_module + "."):
                candidates.append(f"{alias}.{class_name}")
        if not candidates:
            return None
        resolved = self._backend.resolve(
            self._source, candidates, self._search_path
        )
        for candidate, found in zip(candidates, resolved, strict=True):
            if (
                found is not None
                and found.kind == "class"
                and found.full_name == full_name
            ):
                return ast.parse(candidate, mode="eval").body
        return None


def _declared_type(
    values: list[Inferred], scope: _Scope, spellings: _ClassSpellings
) -> ast.expr | None:
    """The annotation for a variable, from the values inferred for it."""
    members: list[ast.expr] = []
    for value in values:
        if value.kind != "instance":
            return None
        if value.full_name.rpartition(".")[2].startswith("_"):
            continue
        member = _member_type(value, scope, spellings)
        if member is None:
            return None
        members.append(member)
    if not members:
        return None
    node = cast(ast.expr, _Normalize().visit(_union(members)))
    if _names_in(node) - scope.allowed_refs or _is_broad(node):
        return None
    return node


def _is_broad(node: ast.expr) -> bool:
    """True when the type names `object` or `Any`, or a union is too wide."""
    if _names_in(node) & _BROAD_TYPES:
        return True
    return any(
        isinstance(n, ast.BinOp)
        and isinstance(n.op, ast.BitOr)
        and len(_union_members(n)) > MAX_UNION_MEMBERS
        for n in ast.walk(node)
    )


def _member_type(
    value: Inferred, scope: _Scope, spellings: _ClassSpellings
) -> ast.expr | None:
    module, _, class_name = value.full_name.rpartition(".")
    if module != _BUILTINS:
        return spellings.spell(value.full_name)
    if class_name == "NoneType":
        return ast.Constant(value=None)
    if class_name not in scope.builtins:
        return None
    bare = ast.Name(id=class_name, ctx=ast.Load())
    hinted = lower_hint(value.hint) if value.hint else None
    # A nested name may be unavailable or a shadowed builtin. The bare
    # container is still true in either case.
    if (
        hinted is None
        or _names_in(hinted) - scope.allowed_refs
        or _names_in(hinted) & (BUILTINS - scope.builtins)
    ):
        return bare
    return hinted


def lower_hint(hint: str) -> ast.expr | None:
    """Rewrite a jedi type hint with builtin generics and `|` unions.

    `List[Union[int, str]]` becomes `list[int | str]`. Returns None when the
    hint is not a Python expression.
    """
    try:
        node = ast.parse(hint, mode="eval").body
    except SyntaxError:
        return None
    return cast(ast.expr, _Normalize().visit(_LowerTyping().visit(node)))


def to_annotation(hint: str, allowed_refs: set[Name]) -> AnnotationData | None:
    """Turn a builtin type hint into an annotation, or None to drop it.

    Drop anything that is not a Python expression or that names something
    outside module scope.
    """
    node = lower_hint(hint)
    if node is None or _names_in(node) - allowed_refs:
        return None
    return _annotation(node)


def _annotation(node: ast.expr) -> AnnotationData:
    return AnnotationData(
        standardize_annotation_quotes(ast.unparse(node)), _names_in(node)
    )


def _names_in(node: ast.expr) -> set[Name]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _union_members(node: ast.expr) -> list[ast.expr]:
    """Flatten `A | B | C` into its members."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union_members(node.left) + _union_members(node.right)
    return [node]


def _union(members: list[ast.expr]) -> ast.expr:
    """`A | B | C` over the distinct members, in first-seen order."""
    distinct: list[ast.expr] = []
    for member in members:
        if all(ast.dump(member) != ast.dump(seen) for seen in distinct):
            distinct.append(member)
    union = distinct[0]
    for extra in distinct[1:]:
        union = ast.BinOp(left=union, op=ast.BitOr(), right=extra)
    return union


class _LowerTyping(ast.NodeTransformer):
    """`typing` spellings to the builtin ones a signature wants."""

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if node.id in _TYPING_TO_BUILTIN:
            return ast.Name(id=_TYPING_TO_BUILTIN[node.id], ctx=ast.Load())
        if node.id == "NoneType":
            return ast.Constant(value=None)
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        self.generic_visit(node)
        if not isinstance(node.value, ast.Name):
            return node
        members = (
            node.slice.elts
            if isinstance(node.slice, ast.Tuple)
            else [node.slice]
        )
        if node.value.id == "Union":
            return _union(members)
        if node.value.id == "Optional":
            return _union([*members, ast.Constant(value=None)])
        return node


class _Normalize(ast.NodeTransformer):
    """Rewrite an inferred type as the declared type a parameter wants.

    `Literal[...]` members widen to their type, so `Literal[1]` is `int`.
    Members that cannot be widened leave the `Literal[...]` as it is. A
    fixed-length tuple longer than `MAX_TUPLE_ELEMENTS` becomes
    `tuple[T, ...]` over the union of its element types, which every such
    tuple satisfies. Unions drop duplicate members.
    """

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.op, ast.BitOr):
            return _union(_union_members(node))
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        self.generic_visit(node)
        if not isinstance(node.value, ast.Name):
            return node
        members = (
            node.slice.elts
            if isinstance(node.slice, ast.Tuple)
            else [node.slice]
        )
        if node.value.id == "Literal":
            widened: list[ast.expr] = []
            for member in members:
                wide = _widen_literal_member(member)
                if wide is None:
                    return node
                widened.append(wide)
            return _union(widened)
        if node.value.id == "tuple" and len(members) > MAX_TUPLE_ELEMENTS:
            if any(
                isinstance(m, ast.Constant) and m.value is Ellipsis
                for m in members
            ):
                return node
            return ast.Subscript(
                value=node.value,
                slice=ast.Tuple(
                    elts=[_union(members), ast.Constant(value=Ellipsis)],
                    ctx=ast.Load(),
                ),
                ctx=ast.Load(),
            )
        return node


def _widen_literal_member(member: ast.expr) -> ast.expr | None:
    if isinstance(member, ast.UnaryOp) and isinstance(member.op, ast.USub):
        member = member.operand
    if isinstance(member, ast.Constant):
        value = member.value
        if value is None:
            return ast.Constant(value=None)
        # NB. Check bool before int, since True is an int.
        if isinstance(value, bool):
            return ast.Name(id="bool", ctx=ast.Load())
        return ast.Name(id=type(value).__name__, ctx=ast.Load())
    # Enum members: `Literal[Color.RED]` widens to `Color`.
    if isinstance(member, ast.Attribute):
        return member.value
    return None
