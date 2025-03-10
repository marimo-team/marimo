# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import os
import re
import textwrap
from typing import Any, Literal, Optional, cast

from marimo import __version__
from marimo._ast.app import App, _AppConfig
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.names import DEFAULT_CELL_NAME
from marimo._ast.transformers import RemoveImportTransformer
from marimo._ast.visitor import Name
from marimo._types.ids import CellId_t

INDENT = "    "
MAX_LINE_LENGTH = 80

NOTICE = "\n".join(
    [
        "# Imports used by your notebook.",
        "# This section is automatically generated by marimo.",
    ]
)


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
) -> str:
    """
    Replaces (...) with the elements in elems, formatted as a tuple.
    Adjusts for multiple lines as needed.
    """
    maybe_indent = indent_text if indent else (lambda x: x)
    if not elems:
        if allowed_naked:
            return maybe_indent(code.replace("(...)", "").rstrip())
        return maybe_indent(code.replace("(...)", "()"))

    if allowed_naked and len(elems) == 1:
        allowed_naked = False
        elems = (f"{elems[0]},",)

    tuple_str = ", ".join(elems)
    if allowed_naked:
        attempt = code.replace("(...)", tuple_str).rstrip()
    else:
        attempt = code.replace("(...)", f"({tuple_str})")

    attempt = maybe_indent(attempt)
    if len(attempt) < MAX_LINE_LENGTH:
        return attempt

    # Edgecase for very long variables
    if len(elems) == 1:
        elems = (elems[0].strip(","),)

    multiline_tuple = "\n".join(
        ["(", indent_text(",\n".join(elems)) + ",", ")"]
    )
    return maybe_indent(code.replace("(...)", multiline_tuple))


def to_decorator(
    config: Optional[CellConfig], fn: Literal["cell", "function"] = "cell"
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


def build_import_section(import_blocks: list[str]) -> str:
    from marimo._utils.formatter import Formatter, ruff

    stripped_block = RemoveImportTransformer("marimo").strip_imports(
        "\n".join(import_blocks)
    )
    if not stripped_block:
        return ""

    code = "\n".join(
        [
            "with marimo.import_guard():",
            indent_text(NOTICE),
            indent_text(stripped_block),
        ]
    )

    stub_cell_id = CellId_t("sub")

    formatted = Formatter(MAX_LINE_LENGTH).format({stub_cell_id: code})
    if not formatted:
        return code
    try:
        # Note F401 strips unused imports, which is this whole block.
        tidied = ruff(formatted, "check", "--fix-only", "--ignore=F401")
        if tidied:
            return tidied[stub_cell_id] + "\n\n"
    # Thrown in WASM
    except OSError:
        pass
    return formatted[stub_cell_id]


def to_functiondef(
    cell: CellImpl,
    name: str,
    allowed_refs: Optional[set[Name]] = None,
    used_refs: Optional[set[Name]] = None,
    fn: Literal["cell"] = "cell",
) -> str:
    # allowed refs are a combination of top level imports and unshadowed
    # builtins.
    # unshadowed builtins is the set of builtins that haven't been
    # overridden (shadowed) by other cells in the app. These names
    # should not be taken as args by a cell's functiondef (since they are
    # already in globals)
    if allowed_refs is None:
        allowed_refs = set(builtins.__dict__.keys())
    refs = tuple(ref for ref in sorted(cell.refs) if ref not in allowed_refs)

    decorator = to_decorator(cell.config, fn=fn)

    prefix = "" if not cell.is_coroutine() else "async "
    signature = format_tuple_elements(f"{prefix}def {name}(...):", refs)

    definition_body = [decorator, signature]
    if body := indent_text(cell.code):
        definition_body.append(body)

    # Used refs are a collection of all the references that cells make to some
    # external call. We collect them such that we can determine if a variable
    # def is actually ever used. This is a nice little trick such that mypy and
    # other static analysis tools can capture unused variables across cells.
    defs: tuple[str, ...] = tuple()
    if cell.defs:
        if used_refs is None:
            defs = tuple(name for name in sorted(cell.defs))
        else:
            defs = tuple(
                name for name in sorted(cell.defs) if name in used_refs
            )

    returns = format_tuple_elements(
        "return (...)", defs, indent=True, allowed_naked=True
    )
    definition_body.append(returns)
    return "\n".join(definition_body)


def to_top_functiondef(
    cell: CellImpl, allowed_refs: Optional[set[str]] = None
) -> str:
    # For the top-level function criteria to be satisfied,
    # the cell, it must pass basic checks in the cell impl.
    if allowed_refs is None:
        allowed_refs = set(builtins.__dict__.keys())
    assert cell.is_toplevel_acceptable(allowed_refs), (
        "Cell is not a top-level function"
    )
    if cell.code:
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
        if config._toplevel_fn:
            updates["_toplevel_fn"] = True

    kwargs = tuple(
        f"{key}={_format_arg(value)}" for key, value in updates.items()
    )
    return format_tuple_elements("app = marimo.App(...)", kwargs)


def _classic_export(
    fndefs: list[str],
    header_comments: Optional[str],
    config: Optional[_AppConfig],
) -> str:
    filecontents = "".join(
        "import marimo"
        + "\n\n"
        + f'__generated_with = "{__version__}"'
        + "\n"
        + generate_app_constructor(config)
        + "\n\n\n"
        + "\n\n\n".join(fndefs)
        + "\n\n\n"
        + 'if __name__ == "__main__":'
        + "\n"
        + indent_text("app.run()")
    )

    if header_comments:
        filecontents = header_comments.rstrip() + "\n\n" + filecontents
    return filecontents + "\n"


def generate_filecontents(
    codes: list[str],
    names: list[str],
    cell_configs: list[CellConfig],
    config: Optional[_AppConfig] = None,
    header_comments: Optional[str] = None,
) -> str:
    """Translates a sequences of codes (cells) to a Python file"""
    # Until an appropriate means of controlling top-level functions exists,
    # Let's keep it disabled by default.
    toplevel_fn = config is not None and config._toplevel_fn

    # Update old internal cell names to the new ones
    for idx, name in enumerate(names):
        if name == "__":
            names[idx] = DEFAULT_CELL_NAME

    # We require 3 sweeps.
    #  - One for compilation and import collection
    #  - One for some basic static determination of top-level functions.
    #  - And a final sweep for cleaner argument requirements
    # (since we now know what's top-level).
    defs: set[Name] = set()
    toplevel_imports: set[Name] = set()
    used_refs: Optional[set[Name]] = set()
    import_blocks: list[str] = []

    definition_stubs: list[Optional[CellImpl]] = [None] * len(codes)
    definitions: list[Optional[str]] = [None] * len(codes)

    cell: Optional[CellImpl]
    for idx, (code, cell_config) in enumerate(zip(codes, cell_configs)):
        try:
            cell = compile_cell(code, cell_id=CellId_t(str(idx))).configure(
                cell_config
            )
            defs |= cell.defs
            assert isinstance(used_refs, set)
            used_refs |= cell.refs
            if cell.import_workspace.is_import_block:
                # maybe a bug, but import_workspace.imported_defs does not
                # contain the information we need.
                toplevel_imports |= cell.defs
                definitions[idx] = to_functiondef(cell, names[idx])
                if toplevel_fn:
                    import_blocks.append(code.strip())
            else:
                definition_stubs[idx] = cell
        except SyntaxError:
            definitions[idx] = generate_unparsable_cell(
                code=code, config=cell_config, name=names[idx]
            )

    unshadowed_builtins = set(builtins.__dict__.keys()) - defs
    allowed_refs = unshadowed_builtins | toplevel_imports

    for idx, cell in enumerate(definition_stubs):
        # We actually don't care about the graph, we just want to see if we can
        # render the top-level functions without a name error.
        # Let graph issues be delegated to the runtime.
        if cell and toplevel_fn and cell.is_toplevel_acceptable(allowed_refs):
            definitions[idx] = to_top_functiondef(cell, allowed_refs)
            definition_stubs[idx] = None
            # Order does matter since feasibly, an app.function could be a
            # decorator for another.
            allowed_refs.add(names[idx])

    # Let's hide the new behavior for now.
    # Removing the toplevel_fn check may produce a bit of churn,
    # so let's release the serialization changes all together.
    if not toplevel_fn:
        allowed_refs = unshadowed_builtins
        used_refs = None

    for idx, cell in enumerate(definition_stubs):
        if cell:
            definitions[idx] = to_functiondef(
                cell, names[idx], allowed_refs, used_refs, fn="cell"
            )

    assert all(isinstance(d, str) for d in definitions)
    cell_blocks: list[str] = cast(list[str], definitions)
    if not toplevel_fn:
        return _classic_export(cell_blocks, header_comments, config)

    filecontents = []
    if header_comments is not None:
        filecontents = [header_comments.rstrip(), ""]

    filecontents.extend(
        [
            "import marimo",
            "",
            build_import_section(import_blocks),
            "",
            f'__generated_with = "{__version__}"',
            generate_app_constructor(config),
            "\n",
            "\n\n\n".join(cell_blocks),
            "\n",
            'if __name__ == "__main__":',
            indent_text("app.run()"),
            "",
        ]
    )
    return "\n".join(filecontents)


class MarimoFileError(Exception):
    pass


def get_app(filename: Optional[str]) -> Optional[App]:
    """Load and return app from a marimo-generated module.

    Args:
        filename: Path to a marimo notebook file (.py or .md)

    Returns:
        The marimo App instance if the file exists and contains valid code,
        None if the file is empty or contains only comments.

    Raises:
        MarimoFileError: If the file exists but doesn't define a valid marimo app
        RuntimeError: If there are issues loading the module
        SyntaxError: If the file contains a syntax error
        FileNotFoundError: If the file doesn't exist
    """
    if filename is None:
        return None

    with open(filename, encoding="utf-8") as f:
        contents = f.read().strip()

    if not contents:
        return None

    if filename.endswith(".md"):
        from marimo._cli.convert.markdown import convert_from_md_to_app

        return convert_from_md_to_app(contents)

    # Below assumes it's a Python file

    # This means it could have only the package dependencies
    # but no actual code yet.
    has_only_comments = all(
        not line.strip() or line.strip().startswith("#")
        for line in contents.splitlines()
    )
    if has_only_comments:
        return None

    spec = importlib.util.spec_from_file_location("marimo_app", filename)
    if spec is None:
        raise RuntimeError("Failed to load module spec")
    marimo_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load module spec's loader")
    spec.loader.exec_module(marimo_app)  # This may throw a SyntaxError
    if not hasattr(marimo_app, "app"):
        raise MarimoFileError(f"{filename} missing attribute `app`.")
    if not isinstance(marimo_app.app, App):
        raise MarimoFileError("`app` attribute must be of type `marimo.App`.")

    app = marimo_app.app
    return app


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
        cast(list[str], codes),
        cast(list[str], names),
        cast(list[CellConfig], configs),
    )


def is_multiline_comment(node: ast.stmt) -> bool:
    """Checks if a node is a docstring or a multiline comment."""
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return True
    return False


def get_header_comments(filename: str) -> Optional[str]:
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
