# Copyright 2024 marimo. All rights reserved.
from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from typing import Any, Callable, Dict, List

from marimo._ast.compiler import compile_cell
from marimo._ast.transformers import NameTransformer
from marimo._ast.visitor import Block, NamedNode, ScopedVisitor
from marimo._convert.utils import generate_from_sources, markdown_to_marimo
from marimo._runtime.dataflow import DirectedGraph
from marimo._utils.variables import is_local

# Define a type for our transform functions
Transform = Callable[[List[str]], List[str]]


def transform_fixup_multiple_definitions(sources: List[str]) -> List[str]:
    """
    Fixup multiple definitions of the same name in different cells,
    by making the name private (underscore) to each cell.

    This only takes effect if the declaration and reference are in
    the same cell.
    """
    try:
        cells = [
            compile_cell(source, cell_id=str(i))
            for i, source in enumerate(sources)
        ]
    except SyntaxError:
        return sources

    graph = DirectedGraph()
    for cell in cells:
        graph.register_cell(cell_id=cell.cell_id, cell=cell)

    multiply_defined_names = graph.get_multiply_defined()
    if not multiply_defined_names:
        return sources

    name_transformations: Dict[str, str] = {}
    for name in multiply_defined_names:
        if not graph.get_referring_cells(name, language="python"):
            name_transformations[name] = (
                "_" + name if not name.startswith("_") else name
            )

    def transform(source: str) -> str:
        try:
            tree = ast.parse(source)
            visitor = NameTransformer(name_transformations)
            transformed_tree = visitor.visit(tree)
            # Don't unparse if no changes were made
            # otherwise we lose comments and formatting
            if visitor.made_changes:
                return ast.unparse(transformed_tree)
            return source
        except SyntaxError:
            return source

    return [transform(source) for source in sources]


def transform_add_marimo_import(sources: List[str]) -> List[str]:
    """
    Add an import statement for marimo if any cell uses
    the `mo.md` or `mo.sql` functions.
    """

    def contains_mo(cell: str) -> bool:
        return cell.startswith("mo.md(") or "mo.sql(" in cell

    if any(contains_mo(cell) for cell in sources):
        return sources + ["import marimo as mo"]

    return sources


def transform_magic_commands(sources: List[str]) -> List[str]:
    """
    Transform Jupyter magic commands to their marimo equivalents
    or comment them out.
    """

    def magic_sql(source: str, command: str) -> str:
        """
        Transform SQL magic into marimo SQL functions.

        %%sql
        SELECT * FROM table

        to

        _df = mo.sql('''
        SELECT * FROM table
        ''')
        """
        del command
        source = source.strip()
        return f'_df = mo.sql("""\n{source}\n""")'

    def magic_remove(source: str, command: str) -> str:
        """
        Remove the magic but keep the source code.
        """
        double = command.startswith("%%")
        if not double:
            return "\n".join(
                [
                    "# magic command not supported in marimo; please file an issue to add support",  # noqa: E501
                    f"# {command + ' ' + source}",
                ]
            )

        result = [
            "# magic command not supported in marimo; please file an issue to add support",  # noqa: E501
            f"# {command}",
        ]
        if source:
            result.append(source)
        return "\n".join(result)

    def magic_already_supported(source: str, command: str) -> str:
        """
        Remove the magic but keep the source code.
        """
        double = command.startswith("%%")
        if not double:
            return f"# {(command + ' ' + source)!r} command supported automatically in marimo"  # noqa: E501

        result = [
            f"# {command!r} command supported automatically in marimo",
        ]
        if source:
            result.append(source)
        return "\n".join(result)

    def magic_mkdir(source: str, command: str) -> str:
        """
        Transform mkdir magic into marimo mkdir functions.

        %mkdir path/to/directory

        to

        import os
        os.makedirs('path/to/directory', exist_ok=True)
        """
        del command
        return f"import os\nos.makedirs({source!r}, exist_ok"

    def magic_cd(source: str, command: str) -> str:
        """
        Transform cd magic into marimo cd functions.

        %cd path/to/directory

        to

        import os
        os.chdir('path/to/directory')
        """
        del command
        return f"import os\nos.chdir({source!r})"

    def magic_html(source: str, command: str) -> str:
        """
        Transform html magic into marimo html functions.

        %html <h1>Heading</h1>

        to

        mo.Html('<h1>Heading</h1>')
        """
        del command
        return f"mo.Html({source!r})"

    def magic_ls(source: str, command: str) -> str:
        """
        Transform ls magic into marimo ls functions.

        %ls

        to

        import os
        os.listdir()
        """
        del command, source
        return "import os\nos.listdir()"

    def magic_bash(source: str, command: str) -> str:
        """
        Transform bash magic into marimo bash functions.

        %bash echo "Hello, world!"

        to

        mo.bash('echo "Hello, world!"')
        """
        del command
        return f"import subprocess\nsubprocess.run({source!r}, shell=True)"

    def magic_env(source: str, command: str) -> str:
        """
        Transform env magic into marimo env functions

        %env VAR_NAME=VALUE

        to

        import os
        os.environ['VAR_NAME'] = 'VALUE'
        """

        del command
        _key, value = source.split("=", 1)
        return f"import os\nos.environ[{_key!r}] = {value!r}"

    def comment_out_code(source: str) -> str:
        if source.strip():
            return "\n".join(f"# {line}" for line in source.split("\n"))
        return source

    magics: Dict[str, Callable[[str, str], str]] = {
        "sql": magic_sql,
        "mkdir": magic_mkdir,
        "cd": magic_cd,
        "html": magic_html,
        "bash": magic_bash,
        "!": magic_bash,
        "ls": magic_ls,
        "load_ext": magic_already_supported,
        "env": magic_env,
        # Already supported in marimo, can just comment out the magic
        "pip": magic_already_supported,
        "matplotlib": magic_already_supported,
        # Remove the magic, but keep the code as is
        "timeit": magic_remove,
        "time": magic_remove,
        # Everything else is not supported and will be commented out
    }

    def transform(cell: str) -> str:
        stripped = cell.strip()

        # Multi-line magic
        if stripped.startswith("%%"):
            magic, rest = stripped.split("\n", 1)
            magic_cmd = magic.strip().split(" ")[0].lstrip("%")
            if magic_cmd in magics:
                return magics[magic_cmd](rest, magic)
            return magic_remove(comment_out_code(rest), magic)

        # Single-line magic
        elif stripped.startswith("%"):
            magic, rest = stripped.split(" ", 1)
            magic_cmd = magic.strip().lstrip("%")
            if magic_cmd in magics:
                return magics[magic_cmd](rest, magic)
            return magic_remove(comment_out_code(rest), magic)

        return cell

    return [transform(cell) for cell in sources]


def transform_exclamation_mark(sources: List[str]) -> List[str]:
    """
    Handle exclamation mark commands.
    """

    def transform(cell: str) -> str:
        if "!pip" in cell:
            cell = cell.replace(
                "!pip",
                "# (use marimo's built-in package management features instead) !pip",  # noqa: E501
            )
        return cell

    return [transform(cell) for cell in sources]


class Renamer:
    def __init__(self, cell_remappings: dict[int, dict[str, str]]) -> None:
        self.cell_remappings = cell_remappings
        self.made_changes = False

    def _maybe_rename(self, cell: int, name: str, is_reference: bool) -> str:
        latest_mapping: dict[str, str] = {}
        until = cell if is_reference else cell + 1
        for idx in range(until):
            if (
                idx in self.cell_remappings
                and name in self.cell_remappings[idx]
            ):
                latest_mapping = self.cell_remappings[idx]
        if name in latest_mapping:
            return latest_mapping[name]
        else:
            return name

    def rename_named_node(
        self, cell: int, node: NamedNode, is_reference: bool
    ) -> None:
        name: str | None = None
        new_name: str | None = None

        if isinstance(node, ast.Name):
            name = node.id
            new_name = self._maybe_rename(cell, name, is_reference)
            node.id = new_name
        elif isinstance(
            node,
            (
                ast.ClassDef,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            name = node.name
            new_name = self._maybe_rename(cell, name, is_reference)
            node.name = new_name
        if sys.version_info >= (3, 10):
            if isinstance(node, (ast.MatchAs, ast.MatchStar)):
                name = node.name
                if name is not None:
                    new_name = self._maybe_rename(cell, name, is_reference)
                    node.name = new_name
            elif isinstance(node, ast.MatchMapping):
                name = node.rest
                if name is not None:
                    new_name = self._maybe_rename(cell, name, is_reference)
                    node.rest = new_name
        if sys.version_info >= (3, 12):
            if isinstance(
                node, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple)
            ):
                name = node.name
                new_name = self._maybe_rename(cell, name, is_reference)
                node.name = new_name

        if not self.made_changes:
            self.made_changes = name != new_name


def _transform_aug_assign(sources: List[str]) -> List[str]:
    new_sources = sources.copy()
    for i, source in enumerate(sources):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        made_changes = False

        class AugAssignTransformer(ast.NodeTransformer):
            def visit_AugAssign(self, node: ast.AugAssign) -> ast.Assign:
                nonlocal made_changes
                made_changes = True
                return ast.Assign(
                    targets=[node.target],
                    value=ast.BinOp(
                        left=node.target, op=node.op, right=node.value
                    ),
                )

        transformed = ast.fix_missing_locations(
            AugAssignTransformer().visit(tree)
        )
        if made_changes:
            new_sources[i] = ast.unparse(transformed)

    return new_sources


def transform_duplicate_definitions(sources: List[str]) -> List[str]:
    """
    Rename variables with duplicate definitions across multiple cells,
    even when the variables are declared in one cell and used in another.

    We assume the notebook was meant to be run top-to-bottom,
    so references to the name will be renamed to the last definition.

    If a new definition is derived from a previous definition,
    then at the top of the cell, we add a new line that assigns
    the new definition to the previous definition.

    ```
    # Cell 1
    a = 1

    # Cell 2
    print(a)

    # Cell 3
    a = 2

    # Cell 4
    a = 3
    print(a)
    ```

    Then we transform it to:

    ```
    # Cell 1
    a = 1

    # Cell 2
    print(a)

    # Cell 3
    a_1 = a
    a_1 = a_1 + 2

    # Cell 4
    a_2 = 3
    print(a_2)
    ```
    """

    # Find all definitions in the AST
    def find_definitions(node: ast.AST) -> List[str]:
        visitor = ScopedVisitor("", ignore_local=True)
        visitor.visit(node)
        # Remove local variables
        defs = list(visitor.defs)
        return [def_ for def_ in defs if not is_local(def_)]

    # Collect all definitions for each cell
    def get_definitions(sources: List[str]) -> Dict[str, List[int]]:
        definitions: Dict[str, List[int]] = defaultdict(list)
        for i, source in enumerate(sources):
            try:
                tree = ast.parse(source)
                for name in find_definitions(tree):
                    definitions[name].append(i)
            except SyntaxError:
                continue
        return definitions

    # Collect all definitions that are duplicates
    def get_duplicates(
        definitions: Dict[str, List[int]],
    ) -> Dict[str, List[int]]:
        return {
            name: cells
            for name, cells in definitions.items()
            if len(cells) > 1
        }

    # Create mappings for renaming duplicates
    def create_name_mappings(
        duplicates: Dict[str, List[int]], definitions: set[str]
    ) -> Dict[int, Dict[str, str]]:
        new_definitions: set[str] = set()
        name_mappings: Dict[int, Dict[str, str]] = defaultdict(dict)
        for name, cells in duplicates.items():
            for i, cell in enumerate(cells[1:], start=1):
                counter = i
                new_name = f"{name}_{counter}"
                while new_name in definitions or new_name in new_definitions:
                    # handles the user defining variables like df_1 in their
                    # original notebook
                    counter += 1
                    new_name = f"{name}_{counter}"
                counter += 1
                name_mappings[cell][name] = new_name
                new_definitions.add(new_name)
        return name_mappings

    definitions = get_definitions(sources)
    duplicates = get_duplicates(definitions)

    if not duplicates:
        return sources

    sources = _transform_aug_assign(sources)

    new_sources: List[str] = sources.copy()
    name_mappings = create_name_mappings(duplicates, set(definitions.keys()))

    for cell_idx, source in enumerate(sources):
        renamer = Renamer(name_mappings)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        def on_def(
            node: NamedNode,
            name: str,
            block_stack: list[Block],
            cell_idx: int = cell_idx,
            renamer: Renamer = renamer,
        ) -> None:
            block_idx = 0 if name in block_stack[-1].global_names else -1
            if block_idx == 0:
                # all top-level definitions are renamed
                renamer.rename_named_node(cell_idx, node, is_reference=False)
            elif block_stack[0].is_defined(name) and not any(
                block.is_defined(name) for block in block_stack[1:]
            ):
                # all ast.LOADs of top-level definitions are defined
                renamer.rename_named_node(cell_idx, node, is_reference=False)

        def on_ref(
            node: NamedNode,
            cell_idx: int = cell_idx,
            renamer: Renamer = renamer,
        ) -> None:
            renamer.rename_named_node(cell_idx, node, is_reference=True)

        visitor = ScopedVisitor(
            ignore_local=True, on_def=on_def, on_ref=on_ref
        )
        new_tree = visitor.visit(tree)

        # Don't unparse if no changes were made
        if not renamer.made_changes:
            new_sources[cell_idx] = source
            continue

        new_source_lines: list[str] = []

        # TODO
        # Add assignments for dependencies
        # for definition, dep in visitor.dependencies.items():
        #    new_source_lines.append(f"{definition} = {dep}")

        # Add the modified source
        new_source_lines.append(ast.unparse(new_tree))
        new_sources[cell_idx] = "\n".join(new_source_lines)

    return new_sources


def transform_cell_metadata(
    sources: List[str], metadata: List[Dict[str, Any]]
) -> List[str]:
    """
    Handle cell metadata, such as tags or cell IDs.
    """
    transformed_sources: List[str] = []
    for source, meta in zip(sources, metadata):
        if "tags" in meta:
            tags = meta["tags"]
            if not tags:
                transformed_sources.append(source)
                continue
            source = f"# Cell tags: {', '.join(tags)}\n{source}"
        transformed_sources.append(source)
    return transformed_sources


def transform_remove_duplicate_imports(sources: List[str]) -> List[str]:
    """
    Remove duplicate imports appearing in any cell.
    """
    imports: set[str] = set()
    new_sources: List[str] = []
    for source in sources:
        new_lines: List[str] = []
        for line in source.split("\n"):
            stripped_line = line.strip()
            if stripped_line.startswith("import ") or stripped_line.startswith(
                "from "
            ):
                if stripped_line not in imports:
                    imports.add(stripped_line)
                    new_lines.append(line)
            else:
                new_lines.append(line)

        new_source = "\n".join(new_lines)
        new_sources.append(new_source.strip())

    return new_sources


def transform_remove_empty_cells(sources: List[str]) -> List[str]:
    """
    Remove empty cells.
    """
    sources = [source for source in sources if source.strip()]
    # Ensure there is at least one cell
    if not sources:
        return [""]
    return sources


def transform_strip_whitespace(sources: List[str]) -> List[str]:
    """
    Strip whitespace from the beginning and end of each cell.
    """
    return [source.strip() for source in sources]


def _transform_sources(
    sources: list[str], metadata: list[dict[str, Any]]
) -> list[str]:
    transforms: List[Transform] = [
        transform_strip_whitespace,
        transform_magic_commands,
        transform_remove_duplicate_imports,
        transform_fixup_multiple_definitions,
        transform_duplicate_definitions,
        lambda s: transform_cell_metadata(s, metadata),
        transform_add_marimo_import,  # may change cell count
        transform_remove_empty_cells,  # may change cell count
    ]

    # Run all the transforms
    for transform in transforms:
        sources = transform(sources)
    return sources


def convert_from_ipynb(raw_notebook: str) -> str:
    notebook = json.loads(raw_notebook)
    sources: List[str] = []
    metadata: List[Dict[str, Any]] = []

    for cell in notebook["cells"]:
        source = (
            "".join(cell["source"])
            if isinstance(cell["source"], list)
            else cell["source"]
        )
        if cell["cell_type"] == "markdown":
            source = markdown_to_marimo(source)
        sources.append(source)
        metadata.append(cell.get("metadata", {}))

    return generate_from_sources(_transform_sources(sources, metadata))
