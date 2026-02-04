# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Union

from marimo._ast.cell import CellConfig
from marimo._ast.compiler import compile_cell
from marimo._ast.transformers import NameTransformer, RemoveImportTransformer
from marimo._ast.variables import is_local
from marimo._ast.visitor import Block, NamedNode, ScopedVisitor
from marimo._convert.common.format import markdown_to_marimo
from marimo._runtime.dataflow import DirectedGraph
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    Header,
    NotebookSerializationV1,
)
from marimo._types.ids import CellId_t

# Define a type for our 1:1 source-only transform functions
Transform = Callable[[list[str]], list[str]]


@dataclass
class CodeCell:
    source: str
    config: CellConfig = field(default_factory=CellConfig)


# Define a type for transforms that add/remove cells
CellsTransform = Callable[[list[CodeCell]], list[CodeCell]]


def transform_fixup_multiple_definitions(sources: list[str]) -> list[str]:
    """
    Fixup multiple definitions of the same name in different cells,
    by making the name private (underscore) to each cell.

    This only takes effect if the declaration and reference are in
    the same cell.
    """
    try:
        cells = [
            compile_cell(source, cell_id=CellId_t(str(i)))
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

    name_transformations: dict[str, str] = {}
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


def transform_add_marimo_import(sources: list[CodeCell]) -> list[CodeCell]:
    """
    Add an import statement for marimo if any cell uses
    the `mo.md` or `mo.sql` functions.
    """

    def contains_mo(cell: str) -> bool:
        return cell.startswith("mo.md(") or "mo.sql(" in cell

    def has_marimo_import(cell: str) -> bool:
        # Quick check
        if "import marimo as mo" not in cell:
            return False

        def is_in_import_line(line: str) -> bool:
            if line.startswith("import marimo as mo"):
                return True
            if line.startswith("import ") or line.startswith("from "):
                return "import marimo as mo" in line
            return False

        # Slow check
        lines = cell.strip().split("\n")
        if any(is_in_import_line(line) for line in lines):
            return True
        return False

    already_has_marimo_import = any(
        has_marimo_import(cell.source) for cell in sources
    )
    if already_has_marimo_import:
        return sources

    if any(contains_mo(cell.source) for cell in sources):
        return [CodeCell("import marimo as mo")] + sources

    return sources


def transform_add_subprocess_import(
    sources: list[CodeCell], exclamation_metadata: ExclamationMarkResult | None
) -> list[CodeCell]:
    """
    Add an import statement for subprocess if any cell uses subprocess.call.
    """
    # Check if subprocess import is needed
    if not exclamation_metadata or not exclamation_metadata.needs_subprocess:
        return sources

    def has_subprocess_import(cell: str) -> bool:
        # Quick check
        if "import subprocess" not in cell:
            return False

        def is_in_import_line(line: str) -> bool:
            stripped = line.strip()
            if stripped.startswith("import subprocess"):
                return True
            return False

        # Slow check
        lines = cell.strip().split("\n")
        if any(is_in_import_line(line) for line in lines):
            return True
        return False

    already_has_subprocess_import = any(
        has_subprocess_import(cell.source) for cell in sources
    )
    if already_has_subprocess_import:
        return sources

    # Add subprocess import at the beginning
    return [CodeCell("import subprocess")] + sources


def transform_magic_commands(sources: list[str]) -> list[str]:
    """
    Transform Jupyter magic commands to their marimo equivalents
    or comment them out.

    In the transformer helper methods, command is the magic command
    starting with either % or %%; source is the args of the command
    for a single line magic or the entire cell source for a double line magic

    For example:

    %load_ext autoreload

    yields command == "%load_ext", source = "autoreload", but

    %%sql
    SELECT * FROM TABLE (
    ...
    )

    yields command == "%%sql", source ==
        SELECT * FROM TABLE (
        ...
        )
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
            return f"# {(command + ' ' + source)!r} command supported automatically in marimo"

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
        return f"import os\nos.makedirs({source!r}, exist_ok=True)"

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

    magics: dict[str, Callable[[str, str], str]] = {
        "sql": magic_sql,
        "mkdir": magic_mkdir,
        "cd": magic_cd,
        "html": magic_html,
        "bash": magic_bash,
        "!": magic_bash,
        "ls": magic_ls,
        "load_ext": magic_remove,
        "env": magic_env,
        # Already supported in marimo, can just comment out the magic
        "pip": magic_already_supported,
        "matplotlib": magic_already_supported,
        "autoreload": magic_already_supported,
        # Remove the magic, but keep the code as is
        "timeit": magic_remove,
        "time": magic_remove,
        # Everything else is not supported and will be commented out
    }

    def transform_single_line_magic(line: str) -> str:
        pieces = line.strip().lstrip("%").split()
        magic_cmd, args = pieces[0], pieces[1:]
        rest = " ".join(args)
        if magic_cmd in magics:
            return magics[magic_cmd](rest, "%" + magic_cmd)
        return magic_remove(rest, "%" + magic_cmd)

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
        lines = stripped.split("\n")
        result = []
        if not any(line.startswith("%") for line in lines):
            return cell

        for line in lines:
            result.append(
                transform_single_line_magic(line)
                if line.startswith("%")
                else line
            )
        return "\n".join(result)

    return [transform(cell) for cell in sources]


@dataclass
class ExclamationCommandResult:
    """Result of processing a single exclamation command."""

    replacement: str
    pip_packages: list[str]
    needs_subprocess: bool


@dataclass
class ExclamationMarkResult:
    """Result of processing all exclamation mark commands in sources."""

    transformed_sources: list[str]
    pip_packages: list[str]
    needs_subprocess: bool


def _normalize_git_url_package(package: str) -> str:
    """
    Normalize git URL packages to PEP 508 format.

    Converts:
        git+https://github.com/user/repo.git
    To:
        repo @ git+https://github.com/user/repo.git

    Returns the package as-is if it's not a git URL.
    """
    # Check if this looks like a git URL or VCS URL
    # Common patterns: git+https://, git+ssh://, git+git://, or any URL ending in .git
    is_git_url = package.startswith("git+") or (
        "://" in package
        and package.rstrip("/").endswith(".git")
        and " @ " not in package
    )

    if is_git_url:
        import urllib.parse

        # Extract the repo name from the URL
        if package.startswith("git+"):
            url_without_prefix = package[4:]  # Remove "git+"
        else:
            url_without_prefix = package

        # Parse the URL to extract the path
        parsed = urllib.parse.urlparse(url_without_prefix)
        path = parsed.path

        # Get the last part of the path as the repo name
        repo_name = path.rstrip("/").split("/")[-1]

        # Remove .git extension if present
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        # If we couldn't extract a name, use a placeholder
        if not repo_name:
            repo_name = "package"

        # Ensure the URL has git+ prefix
        if not package.startswith("git+"):
            package = f"git+{package}"

        return f"{repo_name} @ {package}"

    return package


def _extract_pip_install(
    command_line: str, command_tokens: list[str], indent_level: int = 0
) -> ExclamationCommandResult:
    pip_packages: list[str] = []
    if "install" not in command_tokens:
        return _shlex_to_subprocess_call(command_line, command_tokens)

    install_idx = command_tokens.index("install")

    # Collect packages and items for display, skipping flags
    packages = []  # Actual packages (no templates)
    templates = []  # Template placeholders
    for token in command_tokens[install_idx + 1 :]:
        # Skip flags (starting with -)
        if token.startswith("-"):
            continue
        # Template placeholders stop package collection
        if token.startswith("{") and token.endswith("}"):
            templates.append(token)
            break
        packages.append(token)

    # Normalize git URLs to PEP 508 format
    pip_packages = [_normalize_git_url_package(p) for p in packages]

    # For display: show templates only if there are no real packages
    display_items = packages if packages else templates

    # Comment out the pip command, showing items in comment
    # Add pass for indented commands to prevent empty blocks
    if indent_level > 0:
        replacement = (
            "pass  # packages added via marimo's package management: "
            f"{' '.join(display_items)} !{command_line}"
        )
    else:
        replacement = (
            "# packages added via marimo's package management: "
            f"{' '.join(display_items)} !{command_line}"
        )
    return ExclamationCommandResult(replacement, pip_packages, False)


def _is_compilable_expression(expr: str) -> bool:
    """Check if expression is valid Python that can be compiled.

    Args:
        expr: The expression to check (without surrounding braces)

    Returns:
        True if the expression can be compiled as valid Python, False otherwise
    """
    try:
        compile(expr, "<string>", "eval")
        return True
    except (SyntaxError, ValueError):
        return False


def _shlex_to_subprocess_call(
    command_line: str, command_tokens: list[str]
) -> ExclamationCommandResult:
    """Convert a shell command to subprocess.call([...])

    Template placeholders {expr} are converted to str(expr) if expr is valid Python.
    If any template contains invalid Python, the entire command is commented out.

    Args:
        command_line: The command string
        command_tokens: Tokenized command
    """
    # First pass: check if any template is invalid
    for token in command_tokens:
        if token.startswith("{") and token.endswith("}"):
            expr = token[1:-1]
            if not _is_compilable_expression(expr):
                # Comment out entire command if any template is invalid
                # Always add pass to prevent empty blocks
                return ExclamationCommandResult(
                    f"pass  # !{command_line}\n"
                    f"# Note: Command contains invalid template expression",
                    [],
                    False,  # No subprocess needed
                )

    # Second pass: convert templates to str() calls
    processed_tokens = []
    for token in command_tokens:
        if token.startswith("{") and token.endswith("}"):
            expr = token[1:-1]
            # Convert to str() call
            processed_tokens.append(f"str({expr})")
        else:
            processed_tokens.append(repr(token))

    # Build the subprocess call with processed tokens
    tokens_str = "[" + ", ".join(processed_tokens) + "]"
    command = "\n".join(
        [f"#! {command_line}", f"subprocess.call({tokens_str})"]
    )
    return ExclamationCommandResult(command, [], True)


def _handle_exclamation_command(
    command_line: str, indent_level: int = 0
) -> ExclamationCommandResult:
    """
    Process an exclamation command line.

    Args:
        command_line: The command to process (without the leading !)
        indent_level: Column position of the ! (0 = top-level, >0 = indented)

    Returns: (replacement_text, pip_packages, needs_subprocess)
    """
    import shlex

    # Split command to check first token
    try:
        command_tokens = shlex.split(command_line)
    except ValueError:
        command_tokens = command_line.split()

    if not command_tokens:
        return ExclamationCommandResult(f"# !{command_line}", [], False)

    # scrub past tokens until pip
    # For instance in the case `uv pip install ...`
    for i, token in enumerate(command_tokens):
        if token.startswith("pip"):
            # Pip installs always use marimo's package management (never subprocess)
            return _extract_pip_install(
                command_line, command_tokens[i:], indent_level
            )

    # Replace with subprocess.call()
    return _shlex_to_subprocess_call(command_line, command_tokens)


def _normalize_package_name(name: str) -> str:
    """Normalize a package name per PEP 503.

    PEP 503 specifies that package names should be normalized by:
    - Converting to lowercase
    - Replacing underscores, periods, and consecutive dashes with single dashes

    Args:
        name: Package name to normalize

    Returns:
        Normalized package name
    """
    return re.sub(r"[-_.]+", "-", name.lower())


def _extract_package_name(pkg: str) -> str:
    """Extract and normalize the base package name from a package specification.

    Handles version specifiers, extras, and VCS URLs.
    Returns normalized names per PEP 503.

    Args:
        pkg: Package specification (e.g., "numpy>=1.0", "package[extra]", "name @ git+...")

    Returns:
        Normalized base package name (e.g., "numpy", "package", "name")
    """
    # Handle PEP 508 URL format: "name @ git+..."
    if " @ " in pkg:
        name = pkg.split(" @ ")[0].strip()
        return _normalize_package_name(name)

    # Strip version specifiers and extras
    name = (
        pkg.split("==")[0]
        .split(">=")[0]
        .split("<=")[0]
        .split("~=")[0]
        .split("[")[0]
        .split("<")[0]
        .split(">")[0]
        .strip()
    )
    return _normalize_package_name(name)


def _resolve_pip_packages(packages: list[str]) -> list[str]:
    """Resolve pip packages using uv for validation, returning only direct packages.

    Uses uv pip compile to validate packages and resolve conflicts, but filters
    the output to only include packages that were originally requested (not
    transitive dependencies).

    For git URLs, preserves the full PEP 508 format (e.g., "name @ git+...").

    Args:
        packages: List of package specifications (may have duplicates/conflicts)

    Returns:
        Resolved and sorted list of direct packages only
    """
    if not packages:
        return []

    import subprocess
    import tempfile
    from pathlib import Path

    # Build a mapping from normalized name to original package spec
    # For git URLs, we want to preserve the full URL format
    original_specs: dict[str, str] = {}
    for pkg in packages:
        name = _extract_package_name(pkg)
        # For git URLs (PEP 508 format), preserve the full spec
        if " @ " in pkg:
            original_specs[name] = pkg
        else:
            # For regular packages, just use the normalized name
            original_specs[name] = name

    original_names = set(original_specs.keys())

    # Try using uv pip compile to validate/resolve conflicts
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.in"
            out_file = Path(tmpdir) / "requirements.txt"

            # Write packages to temp file
            req_file.write_text("\n".join(packages))

            # Run uv pip compile
            result = subprocess.run(
                [
                    "uv",
                    "pip",
                    "compile",
                    str(req_file),
                    "--output-file",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and out_file.exists():
                # Parse resolved requirements, filtering to only direct packages
                resolved = []
                for line in out_file.read_text().splitlines():
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith("#"):
                        # Extract package name
                        pkg_name = _extract_package_name(line)
                        # Only include if it was in the original request
                        if pkg_name in original_names:
                            # Use the original spec (preserves git URLs)
                            resolved.append(original_specs[pkg_name])
                return sorted(set(resolved))
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # uv not available or failed, fall through to unpinning
        pass

    # Fallback: deduplicate and return original specs
    return sorted(original_specs.values())


def transform_exclamation_mark(sources: list[str]) -> ExclamationMarkResult:
    """
    Implementation of exclamation mark transform.

    Uses tokenization to detect: newline + "!" + optional whitespace + command
    """
    import io
    from tokenize import (
        COMMENT,
        ENCODING,
        ERRORTOKEN,
        INDENT,
        NEWLINE,
        NL,
        OP,
        TokenInfo,
        tokenize,
    )

    all_pip_packages: list[str] = []
    any_needs_subprocess = False
    transformed_sources: list[str] = []

    for cell in sources:
        try:
            tokens = list(tokenize(io.BytesIO(cell.encode("utf-8")).readline))
        except Exception:
            # If tokenization fails, return cell unchanged
            transformed_sources.append(cell)
            continue

        # Track which lines have ! commands and their replacements
        line_replacements: dict[int, str] = {}  # line_num -> replacement_text
        in_exclaim = False
        exclaim_tokens: list[TokenInfo] = []
        trailing_comment = None
        exclaim_line_num = None
        exclaim_indent_level = 0

        for i, token in enumerate(tokens):
            # Check for newline + ! pattern (or ! at start after ENCODING)
            # ! is OP in Python 3.12+ and ERRORTOKEN in Python 3.10/3.11
            # Can also appear after INDENT for indented cells
            if (
                token.string == "!"
                and token.type in (OP, ERRORTOKEN)
                and i > 0
                and tokens[i - 1].type in (NEWLINE, NL, ENCODING, INDENT)
            ):
                in_exclaim = True
                exclaim_tokens = []
                trailing_comment = None
                exclaim_line_num = token.start[0]
                exclaim_indent_level = token.start[
                    1
                ]  # Column position = indentation
                continue  # Skip the ! token

            elif in_exclaim:
                if token.type in (NEWLINE, NL):
                    # End of exclamation command - process it
                    # Check if last token was a comment
                    if exclaim_tokens and exclaim_tokens[-1].type == COMMENT:
                        trailing_comment = exclaim_tokens.pop()

                    # Extract command from collected tokens by reconstructing from source
                    if exclaim_tokens:
                        # Reconstruct command from original source using token positions
                        # This properly handles multi-line commands with backslash continuations
                        first_token = exclaim_tokens[0]
                        last_token = exclaim_tokens[-1]

                        # Get line numbers (1-indexed)
                        start_line_num = first_token.start[0]
                        end_line_num = last_token.end[0]
                        start_col = first_token.start[1]
                        end_col = last_token.end[1]

                        # Split cell into lines for extraction
                        cell_lines = cell.split("\n")

                        if start_line_num == end_line_num:
                            # Single line command
                            command_line = cell_lines[start_line_num - 1][
                                start_col:end_col
                            ].strip()
                        else:
                            # Multi-line command - extract across lines
                            parts = []
                            # First line
                            parts.append(
                                cell_lines[start_line_num - 1][start_col:]
                            )
                            # Middle lines
                            for line_idx in range(
                                start_line_num, end_line_num - 1
                            ):
                                parts.append(cell_lines[line_idx])
                            # Last line
                            parts.append(
                                cell_lines[end_line_num - 1][:end_col]
                            )

                            # Join and remove backslash continuations
                            full_text = "\n".join(parts)
                            # Remove backslash line continuations
                            command_line = full_text.replace(
                                "\\\n", " "
                            ).strip()
                            # Normalize whitespace
                            command_line = " ".join(command_line.split())
                    else:
                        command_line = ""

                    result = _handle_exclamation_command(
                        command_line, indent_level=exclaim_indent_level
                    )

                    all_pip_packages.extend(result.pip_packages)
                    any_needs_subprocess |= result.needs_subprocess

                    if exclaim_line_num is not None:
                        line_replacements[exclaim_line_num] = (
                            result.replacement
                        )
                        # Store replacement for this line
                        if trailing_comment:
                            line_replacements[exclaim_line_num] += (
                                "\n" + trailing_comment.string
                            )

                        # For multi-line commands, mark continuation lines for removal
                        if exclaim_tokens:
                            last_token = exclaim_tokens[-1]
                            end_line_num = last_token.end[0]
                            # Mark all continuation lines (after the first) as removed
                            for line_num in range(
                                exclaim_line_num + 1, end_line_num + 1
                            ):
                                line_replacements[line_num] = None  # type: ignore

                    in_exclaim = False
                else:
                    # Collect tokens that are part of the command
                    exclaim_tokens.append(token)

        # Apply replacements to the cell
        if line_replacements:
            lines = cell.split("\n")
            new_lines = []
            for line_num, line in enumerate(lines, start=1):
                if line_num in line_replacements:
                    replacement = line_replacements[line_num]
                    # None means skip this line (multi-line continuation)
                    if replacement is None:
                        continue
                    # Preserve indentation from original line
                    indent = (len(line) - len(line.lstrip())) * " "
                    replacements = replacement.split("\n")
                    # Add indentation to replacement
                    indented_replacement = [
                        indent + replacement for replacement in replacements
                    ]
                    new_lines.extend(indented_replacement)
                else:
                    new_lines.append(line)
            transformed_sources.append("\n".join(new_lines))
        else:
            transformed_sources.append(cell)

    # Resolve packages using uv (or unpin if unavailable)
    resolved_packages = _resolve_pip_packages(all_pip_packages)

    return ExclamationMarkResult(
        transformed_sources=transformed_sources,
        pip_packages=resolved_packages,
        needs_subprocess=any_needs_subprocess,
    )


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


def _transform_aug_assign(sources: list[str]) -> list[str]:
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


def transform_duplicate_definitions(sources: list[str]) -> list[str]:
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
    def find_definitions(node: ast.AST) -> list[str]:
        visitor = ScopedVisitor("", ignore_local=True)
        visitor.visit(node)
        # Remove local variables
        defs = list(visitor.defs)
        return [def_ for def_ in defs if not is_local(def_)]

    # Collect all definitions for each cell
    def get_definitions(sources: list[str]) -> dict[str, list[int]]:
        definitions: dict[str, list[int]] = defaultdict(list)
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
        definitions: dict[str, list[int]],
    ) -> dict[str, list[int]]:
        return {
            name: cells
            for name, cells in definitions.items()
            if len(cells) > 1
        }

    # Create mappings for renaming duplicates
    def create_name_mappings(
        duplicates: dict[str, list[int]], definitions: set[str]
    ) -> dict[int, dict[str, str]]:
        new_definitions: set[str] = set()
        name_mappings: dict[int, dict[str, str]] = defaultdict(dict)
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

    new_sources: list[str] = sources.copy()
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


def bind_cell_metadata(
    sources: list[str], metadata: list[dict[str, Any]], hide_flags: list[bool]
) -> list[CodeCell]:
    """
    One-time transformation that binds sources and (ipynb) metadata into CodeCell objects.

    This marks the boundary between source-only transformations and cell-level transformations.

    - If "hide-cell" is present in the tags, the cell is marked hidden (and removed)
    - Remaining tags (if any) are inserted as a comment at the top of the source.
    - If marimo-specific metadata is present, it is used to restore cell config.
    """
    cells: list[CodeCell] = []
    for source, meta, hide_code in zip(sources, metadata, hide_flags):
        tags: set[str] = set(meta.get("tags", []))
        if "hide-cell" in tags:
            tags.discard("hide-cell")
            hide_code = True
        if tags:
            source = f"# Cell tags: {', '.join(sorted(tags))}\n{source}"

        # Extract marimo-specific cell config if present
        marimo_meta = meta.get("marimo", {})
        marimo_config = marimo_meta.get("config", {})

        # Merge marimo config with existing flags
        # marimo config takes precedence for hide_code if present
        if "hide_code" in marimo_config:
            hide_code = marimo_config["hide_code"]

        cells.append(
            CodeCell(
                source=source,
                config=CellConfig(
                    hide_code=hide_code,
                    column=marimo_config.get("column"),
                    disabled=marimo_config.get("disabled", False),
                ),
            )
        )
    return cells


def transform_remove_duplicate_imports(sources: list[str]) -> list[str]:
    """
    Remove duplicate imports appearing in any cell.
    """
    imports: set[str] = set()
    new_sources: list[str] = []
    for source in sources:
        try:
            cell = compile_cell(source, cell_id=CellId_t("temp"))
        except SyntaxError:
            new_sources.append(source)
            continue
        scoped = set()
        for var, instances in cell.variable_data.items():
            for instance in instances:
                if (
                    var in imports or var in scoped
                ) and instance.kind == "import":
                    # If it's not in global imports, we keep one instance
                    keep_one = var not in imports
                    transformer = RemoveImportTransformer(
                        var, keep_one=keep_one
                    )
                    source = transformer.strip_imports(source)
                scoped.add(var)
        imports.update(scoped)
        new_sources.append(source)

    return new_sources


def transform_remove_empty_cells(cells: list[CodeCell]) -> list[CodeCell]:
    """
    Remove empty cells.
    """
    sources = [cell for cell in cells if cell.source.strip()]
    # Ensure there is at least one cell
    if not sources:
        return [CodeCell("")]
    return sources


def transform_strip_whitespace(sources: list[str]) -> list[str]:
    """
    Strip whitespace from the beginning and end of each cell.
    """
    return [source.strip() for source in sources]


def extract_inline_meta(script: str) -> tuple[str | None, str]:
    """
    Extract PEP 723 metadata from a Python source.

    Returns a tuple of the metadata comment and the remaining script.
    """
    if match := re.search(
        r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$",
        script,
    ):
        meta_comment = match.group(0)
        return meta_comment, script.replace(meta_comment, "").strip()
    return None, script


def build_metadata(
    old_metadata: str | None,
    extra_metadata: ExclamationMarkResult | None = None,
) -> str:
    """
    Build PEP 723 metadata, adding pip packages if found.

    Uses PyProjectReader utilities to parse existing metadata and properly
    merge dependencies.
    """
    from marimo._utils.inline_script_metadata import PyProjectReader
    from marimo._utils.scripts import write_pyproject_to_script

    # If no exclamation mark processing happened or no packages found
    if not extra_metadata or not extra_metadata.pip_packages:
        return old_metadata or ""

    pip_packages = extra_metadata.pip_packages

    # Parse existing metadata if present
    if old_metadata:
        reader = PyProjectReader.from_script(old_metadata)
        existing_deps = reader.dependencies

        # Merge new pip packages with existing dependencies
        merged_deps = list(set(existing_deps + pip_packages))

        # Update the project dict with merged dependencies
        project = reader.project.copy()
        project["dependencies"] = merged_deps
    else:
        # Create new project dict
        project = {"dependencies": pip_packages}

    # Convert project dict to PEP 723 format using utility
    return write_pyproject_to_script(project)


def _transform_sources(
    sources: list[str], metadata: list[dict[str, Any]], hide_flags: list[bool]
) -> tuple[list[CodeCell], ExclamationMarkResult | None]:
    """
    Process raw sources and metadata into finalized cells.

    This pipeline runs in three stages:
    1. Source-only transforms (e.g., stripping whitespace, handling magics)
    2. A one-time binding of sources and metadata.
    3. Cell-level transforms (e.g., inserting imports, removing empty cells)

    After this step, cells are ready for execution or rendering.

    Returns:
        A tuple of (cells, exclamation_metadata) where exclamation_metadata
        contains pip packages and subprocess import information.
    """
    from marimo._convert.common.comment_preserver import CommentPreserver

    # Define transforms that don't need comment preservation
    simple_transforms = [
        transform_strip_whitespace,
        transform_magic_commands,
    ]

    # Define transforms that should preserve comments (excluding exclamation_mark)
    comment_preserving_transforms = [
        transform_remove_duplicate_imports,
        transform_fixup_multiple_definitions,
        transform_duplicate_definitions,
    ]

    # Run simple transforms first (no comment preservation needed)
    for source_transform in simple_transforms:
        new_sources = source_transform(sources)
        assert len(new_sources) == len(sources), (
            f"{source_transform.__name__} changed cell count"
        )
        sources = new_sources

    # Create comment preserver from the simplified sources
    comment_preserver = CommentPreserver(sources)

    # Run comment-preserving transforms
    for base_transform in comment_preserving_transforms:
        transform = comment_preserver(base_transform)
        new_sources = transform(sources)
        assert len(new_sources) == len(sources), (
            f"{base_transform.__name__} changed cell count"
        )
        sources = new_sources

    # Handle exclamation_mark specially since it returns ExclamationMarkResult
    exclamation_result = transform_exclamation_mark(sources)
    sources = exclamation_result.transformed_sources
    exclamation_metadata = exclamation_result

    cells = bind_cell_metadata(sources, metadata, hide_flags)

    # may change cell count
    cells = transform_add_subprocess_import(cells, exclamation_metadata)
    cells = transform_add_marimo_import(cells)
    cells = transform_remove_empty_cells(cells)

    return cells, exclamation_metadata


def convert_from_ipynb_to_notebook_ir(
    raw_notebook: str,
) -> NotebookSerializationV1:
    """
    Convert a raw notebook to a NotebookSerializationV1 object.
    """
    notebook = json.loads(raw_notebook)

    # Extract notebook-level marimo metadata if present
    notebook_metadata = notebook.get("metadata", {})
    marimo_nb_meta = notebook_metadata.get("marimo", {})
    app_config = marimo_nb_meta.get("app_config", {})
    stored_header = marimo_nb_meta.get("header")

    sources: list[str] = []
    metadata: list[dict[str, Any]] = []
    hide_flags: list[bool] = []
    inline_meta: Union[str, None] = None

    for cell in notebook["cells"]:
        source = (
            "".join(cell["source"])
            if isinstance(cell["source"], list)
            else cell["source"]
        )
        is_markdown: bool = cell["cell_type"] == "markdown"
        if is_markdown:
            source = markdown_to_marimo(source)
        elif inline_meta is None:
            # Eagerly find PEP 723 metadata, first match wins
            inline_meta, source = extract_inline_meta(source)

        if source:
            sources.append(source)
            metadata.append(cell.get("metadata", {}))
            hide_flags.append(is_markdown)

    transformed_cells, extra_metadata = _transform_sources(
        sources, metadata, hide_flags
    )

    # Use stored header if available, otherwise build from inline_meta
    # stored_header takes precedence when present (even if empty string)
    if stored_header is not None:
        header_value = stored_header
    else:
        header_value = build_metadata(inline_meta, extra_metadata)

    return NotebookSerializationV1(
        app=AppInstantiation(options=app_config),
        header=Header(value=header_value),
        cells=[
            CellDef(
                code=cell.source,
                options=cell.config.asdict(),
            )
            for cell in transformed_cells
        ],
    )
