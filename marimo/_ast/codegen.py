# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import json
import os
import re
import sys
import textwrap
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo import __version__
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.names import DEFAULT_CELL_NAME, SETUP_CELL_NAME
from marimo._ast.toplevel import TopLevelExtraction, TopLevelStatus
from marimo._ast.variables import BUILTINS
from marimo._ast.visitor import Name, VariableData
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

Cls: TypeAlias = type

INDENT = "    "
MAX_LINE_LENGTH = 80

BRACES: dict[Literal["(", "["], tuple[str, str]] = {
    "(": ("(", ")"),
    "[": ("[", "]"),
}

Decorators = Literal["cell", "function", "class_definition"]


def pop_setup_cell(
    code: list[str],
    names: list[str],
    configs: list[CellConfig],
) -> Optional[CellImpl]:
    # Find the cell named setup, compile, and remove the index from all lists.
    if SETUP_CELL_NAME not in names:
        return None
    setup_index = names.index(SETUP_CELL_NAME)
    try:
        cell = compile_cell(
            code[setup_index], cell_id=CellId_t(SETUP_CELL_NAME)
        ).configure(configs[setup_index])
    except SyntaxError:
        return None
    code.pop(setup_index)
    names.pop(setup_index)
    configs.pop(setup_index)
    return cell


def indent_text(text: str) -> str:
    return textwrap.indent(text, INDENT)


def _format_arg(arg: Any) -> str:
    if isinstance(arg, str):
        return f'"{arg}"'.replace("\\", "\\\\")
    elif isinstance(arg, list):
        return f"[{', '.join([_format_arg(item) for item in arg])}]"
    else:
        return str(arg)


def format_tuple_elements(
    code: str,
    elems: tuple[str, ...],
    indent: bool = False,
    allowed_naked: bool = False,
    brace: Literal["(", "["] = "(",
) -> str:
    """
    Replaces (...) with the elements in elems, formatted as a tuple.
    Adjusts for multiple lines as needed.
    """
    left, right = BRACES[brace]
    maybe_indent = indent_text if indent else (lambda x: x)
    if not elems:
        if allowed_naked:
            return maybe_indent(code.replace("(...)", "").rstrip())
        return maybe_indent(code.replace("(...)", left + right))

    if allowed_naked and len(elems) == 1:
        allowed_naked = False
        elems = (f"{elems[0]},",)

    tuple_str = ", ".join(elems)
    if allowed_naked:
        attempt = code.replace("(...)", tuple_str).rstrip()
    else:
        attempt = code.replace("(...)", f"{left}{tuple_str}{right}")

    attempt = maybe_indent(attempt)
    if len(attempt) < MAX_LINE_LENGTH:
        return attempt

    # Edgecase for very long variables
    if len(elems) == 1:
        elems = (elems[0].strip(","),)

    multiline_tuple = "\n".join(
        [left, indent_text(",\n".join(elems)) + ",", right]
    )
    return maybe_indent(code.replace("(...)", multiline_tuple))


def to_decorator(
    config: Optional[CellConfig],
    fn: Decorators = "cell",
) -> str:
    if config is None:
        return f"@app.{fn}"

    # Removed defaults. If the cell's config is the default config,
    # don't include it in the decorator.
    if not config.disabled:
        del config.disabled
    if not config.hide_code:
        del config.hide_code
    if not isinstance(config.column, int):
        del config.column

    if config == CellConfig():
        return f"@app.{fn}"
    else:
        return format_tuple_elements(
            f"@app.{fn}(...)",
            tuple(f"{key}={value}" for key, value in config.__dict__.items()),
        )


def build_setup_section(setup_cell: Optional[CellImpl]) -> str:
    if setup_cell is None:
        return ""
    block = setup_cell.code
    if not block.strip():
        return ""
    prefix = "" if not setup_cell.is_coroutine() else "async "

    has_only_comments = all(
        not line.strip() or line.strip().startswith("#")
        for line in setup_cell.code.splitlines()
    )
    # Fails otherwise
    if has_only_comments:
        block += "\npass"

    return "\n".join(
        [
            f"{prefix}with app.setup:",
            indent_text(block),
            "\n",
        ]
    )


def to_annotated_string(
    variable_data: dict[Name, VariableData],
    names: tuple[Name, ...],
    allowed_refs: set[Name],
) -> dict[str, str]:
    """Checks relevant variables for annotation data, and if found either
    represents the type directly or as a string (as a safety measure)"""
    response: dict[str, str] = {}
    if not variable_data:
        return response
    for name in names:
        if name in variable_data and variable_data[name]:
            variable = variable_data[name]
            annotation = variable.annotation_data
            if annotation:
                if annotation.refs - allowed_refs:
                    response[name] = f'"{annotation.repr}"'
                else:
                    response[name] = annotation.repr
    return response


def to_functiondef(
    cell: CellImpl,
    name: str,
    allowed_refs: Optional[set[Name]] = None,
    used_refs: Optional[set[Name]] = None,
    fn: Literal["cell"] = "cell",
    variable_data: Optional[dict[str, VariableData]] = None,
) -> str:
    # allowed refs are a combination of top level imports and unshadowed
    # builtins.
    # unshadowed builtins is the set of builtins that haven't been
    # overridden (shadowed) by other cells in the app. These names
    # should not be taken as args by a cell's functiondef (since they are
    # already in globals)
    if allowed_refs is None:
        allowed_refs = BUILTINS
    refs = tuple(ref for ref in sorted(cell.refs) if ref not in allowed_refs)

    # Check to see if any of the refs have an explicit type assigned to them.
    annotation_lookups = to_annotated_string(
        variable_data or {}, refs, allowed_refs
    )
    refs = tuple(
        f"{ref}: {annotation_lookups[ref]}"
        if ref in annotation_lookups
        else ref
        for ref in refs
    )

    # Used refs are a collection of all the references that cells make to some
    # external call. We collect them such that we can determine if a variable
    # def is actually ever used. This is a nice little trick such that mypy and
    # other static analysis tools can capture unused variables across cells.
    defs: tuple[str, ...] = tuple()
    if cell.defs:
        # There are possible name error cases where a cell defines, and also
        # requires a variable. We remove defs from the signature such that
        # this causes a lint error in pyright.
        if used_refs is None:
            defs = tuple(name for name in sorted(cell.defs))
        else:
            defs = tuple(
                name for name in sorted(cell.defs) if name in used_refs
            )

    decorator = to_decorator(cell.config, fn=fn)
    prefix = "" if not cell.is_coroutine() else "async "
    signature = format_tuple_elements(f"{prefix}def {name}(...):", refs)

    definition_body = [decorator, signature]
    if body := indent_text(cell.code):
        definition_body.append(body)

    returns = format_tuple_elements(
        "return (...)",
        defs,
        indent=True,
        allowed_naked=True,
        # maybe consider "return Edges(...)"
        # Such that the return type can simply be 'Edges'
    )
    definition_body.append(returns)
    return "\n".join(definition_body)


def to_top_functiondef(
    cell: CellImpl, allowed_refs: Optional[set[str]] = None
) -> str:
    # For the top-level function criteria to be satisfied,
    # the cell, it must pass basic checks in the cell impl.
    if allowed_refs is None:
        allowed_refs = BUILTINS
    toplevel_var = cell.toplevel_variable

    assert toplevel_var, "Cell is not a top-level function"
    if cell.code:
        assert toplevel_var.kind in ("function", "class"), (
            "Unexpected cell kind, please report an issue to github.com/marimo-team/marimo"
        )
        if toplevel_var.kind == "class":
            decorator = to_decorator(cell.config, fn="class_definition")
        else:
            decorator = to_decorator(cell.config, fn="function")
        return "\n".join([decorator, cell.code.strip()])
    return ""


def generate_unparsable_cell(
    code: str, name: Optional[str], config: CellConfig
) -> str:
    text = ["app._unparsable_cell("]
    # escape double quotes to not interfere with string
    quote_escaped_code = code.replace('"', '\\"')
    # use r-string to handle backslashes (don't want to write
    # escape characters, want to actually write backslash characters)
    code_as_str = f'r"""\n{quote_escaped_code}\n"""'

    flags = {}
    if config != CellConfig():
        flags = dict(config.__dict__)

    if name is not None:
        flags["name"] = name

    kwargs = ", ".join(
        [f"{key}={_format_arg(value)}" for key, value in flags.items()]
    )
    if kwargs:
        text.extend([indent_text(f"{code_as_str},"), indent_text(kwargs)])
    else:
        text.append(indent_text(code_as_str))

    text.append(")")

    return "\n".join(text)


def serialize_cell(
    extraction: TopLevelExtraction, status: TopLevelStatus
) -> str:
    if status.is_unparsable:
        return generate_unparsable_cell(
            code=status.code, config=status.cell_config, name=status.name
        )
    cell = status._cell
    assert cell is not None
    if status.is_cell:
        return to_functiondef(
            cell,
            status.name,
            # There are possible NameError cases where a cell defines and also
            # requires a variable. We remove defs from the signature such that
            # this causes a lint error in programs like pyright.
            extraction.allowed_refs | cell.defs,
            extraction.used_refs,
            fn="cell",
            variable_data=extraction.variables,
        )
    elif status.is_toplevel:
        return to_top_functiondef(cell, extraction.allowed_refs)
    else:
        raise ValueError("Unknown cell status, please report this issue.")


def generate_app_constructor(config: Optional[_AppConfig]) -> str:
    default_config = _AppConfig().asdict()
    updates = {}
    # only include a config setting if it's not a default setting, to
    # avoid unnecessary edits to the app file
    if config is not None:
        updates = config.asdict()
        for key in default_config:
            if updates[key] == default_config[key]:
                updates.pop(key)

    kwargs = tuple(
        f"{key}={_format_arg(value)}" for key, value in updates.items()
    )
    return format_tuple_elements("app = marimo.App(...)", kwargs)


def generate_filecontents(
    codes: list[str],
    names: list[str],
    cell_configs: list[CellConfig],
    config: Optional[_AppConfig] = None,
    header_comments: Optional[str] = None,
) -> str:
    """Translates a sequences of codes (cells) to a Python file"""
    # Update old internal cell names to the new ones
    for idx, name in enumerate(names):
        if name == "__":
            names[idx] = DEFAULT_CELL_NAME

    setup_cell = pop_setup_cell(codes, names, cell_configs)
    toplevel_defs: set[Name] = set()
    if setup_cell:
        toplevel_defs = set(setup_cell.defs)
    extraction = TopLevelExtraction(codes, names, cell_configs, toplevel_defs)
    cell_blocks = [serialize_cell(extraction, status) for status in extraction]

    filecontents = []
    if header_comments is not None:
        filecontents = [header_comments.rstrip(), ""]

    filecontents.extend(
        [
            "import marimo",
            "",
            f'__generated_with = "{__version__}"',
            generate_app_constructor(config),
            "",
            build_setup_section(setup_cell),
            "\n\n\n".join(cell_blocks),
            "\n",
            'if __name__ == "__main__":',
            indent_text("app.run()"),
            "",
        ]
    )
    return "\n".join(filecontents).lstrip()


def recover(filename: str) -> str:
    """Generate a module for code recovered from a disconnected frontend"""
    with open(filename, encoding="utf-8") as f:
        contents = f.read()
    cells = json.loads(contents)["cells"]
    codes, names, configs = tuple(
        zip(
            *[
                (
                    cell["code"],
                    cell["name"],
                    cell["config"] if "config" in cell else CellConfig(),
                )
                for cell in cells
            ]
        )
    )
    return generate_filecontents(
        cast(list[str], list(codes)),
        cast(list[str], list(names)),
        cast(list[CellConfig], list(configs)),
    )


def is_multiline_comment(node: ast.stmt) -> bool:
    """Checks if a node is a docstring or a multiline comment."""
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return True
    return False


def get_header_comments(filename: str | Path) -> Optional[str]:
    """Gets the header comments from a file. Returns
    None if the file does not exist or the header is
    invalid, which is determined by:
        1. If the file is does not contain the marimo
            import statement
        2. If the section before the marimo import
            statement contains any non-comment code
    """

    if not os.path.exists(filename):
        return None

    with open(filename, encoding="utf-8") as f:
        contents = f.read()

    if "import marimo" not in contents:
        return None
    header, _ = re.split(
        r"^import marimo", contents, maxsplit=1, flags=re.MULTILINE
    )

    # Ensure the header only contains non-executable code
    # ast parses out single line comments, so we only
    # need to check that every node is not a multiline comment
    module = ast.parse(header)
    if any(not is_multiline_comment(node) for node in module.body):
        return None

    return header
