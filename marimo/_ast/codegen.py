# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import builtins
import importlib.util
import json
import os
from typing import TYPE_CHECKING, Any, List, Optional, Union, cast

from marimo import __version__
from marimo._ast.app import App, _AppConfig
from marimo._ast.cell import CellConfig, CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.visitor import Name

if TYPE_CHECKING:
    from collections.abc import Sequence

INDENT = "    "
MAX_LINE_LENGTH = 80


def indent_text(text: str) -> str:
    return "\n".join(
        [INDENT + line if line else line for line in text.split("\n")]
    )


def _multiline_tuple(elems: Sequence[str]) -> str:
    if elems:
        return "(" + "\n" + indent_text(",\n".join(elems)) + ",\n)"
    else:
        return "()"


def _to_decorator(config: Optional[CellConfig]) -> str:
    if config is None:
        return "@app.cell"

    # Removed defaults. If the cell's config is the default config,
    # don't include it in the decorator.
    if not config.disabled:
        del config.disabled
    if not config.hide_code:
        del config.hide_code

    if config == CellConfig():
        return "@app.cell"
    else:
        return (
            "@app.cell("
            + ", ".join(
                f"{key}={value}" for key, value in config.__dict__.items()
            )
            + ")"
        )


def to_functiondef(
    cell: CellImpl, name: str, unshadowed_builtins: Optional[set[Name]] = None
) -> str:
    # unshadowed builtins is the set of builtins that haven't been
    # overridden (shadowed) by other cells in the app. These names
    # should not be taken as args by a cell's functiondef (since they are
    # already in globals)
    if unshadowed_builtins is None:
        unshadowed_builtins = set(builtins.__dict__.keys())
    refs = [ref for ref in sorted(cell.refs) if ref not in unshadowed_builtins]
    args = ", ".join(refs)

    decorator = _to_decorator(cell.config)
    signature = f"def {name}({args}):"
    prefix = "" if not cell.is_coroutine() else "async "
    if len(INDENT + prefix + signature) >= MAX_LINE_LENGTH:
        signature = f"def {name}{_multiline_tuple(refs)}:"
    signature = prefix + signature

    fndef = decorator + "\n" + signature + "\n"
    body = indent_text(cell.code)
    if body:
        fndef += body + "\n"

    if cell.defs:
        defs = tuple(name for name in sorted(cell.defs))
        returns = INDENT + "return "
        if len(cell.defs) == 1:
            returns += f"{defs[0]},"
        else:
            returns += ", ".join(defs)
        fndef += (
            returns
            if len(INDENT + returns) <= MAX_LINE_LENGTH
            else (indent_text("return " + _multiline_tuple(defs)))
        )
    else:
        fndef += INDENT + "return"
    return fndef


def generate_unparsable_cell(
    code: str, name: Optional[str], config: CellConfig
) -> str:
    # escape double quotes to not interfere with string
    quote_escaped_code = code.replace('"', '\\"')
    # use r-string to handle backslashes (don't want to write
    # escape characters, want to actually write backslash characters)
    code_as_str = f'r"""\n{quote_escaped_code}\n"""'
    text = "app._unparsable_cell(\n" + indent_text(code_as_str)
    if name is not None:
        text += ",\n" + INDENT + f'name="{name}"'
    if config != CellConfig():
        text += (
            ",\n"
            + INDENT
            + ", ".join(
                f"{key}={value}" for key, value in config.__dict__.items()
            )
        )
    text += "\n)"
    return text


def generate_app_constructor(config: Optional[_AppConfig]) -> str:
    def _format_arg(arg: Any) -> str:
        if isinstance(arg, str):
            return f'"{arg}"'
        else:
            return str(arg)

    default_config = _AppConfig().asdict()
    updates = {}
    # only include a config setting if it's not a default setting, to
    # avoid unnecessary edits to the app file
    if config is not None:
        updates = config.asdict()
        for key in default_config:
            if updates[key] == default_config[key]:
                updates.pop(key)

    kwargs = [f"{key}={_format_arg(value)}" for key, value in updates.items()]
    app_constructor = "app = marimo.App(" + ", ".join(kwargs) + ")"
    if len(app_constructor) >= MAX_LINE_LENGTH:
        app_constructor = "app = marimo.App" + _multiline_tuple(kwargs)
    return app_constructor


def generate_filecontents(
    codes: list[str],
    names: list[str],
    cell_configs: list[CellConfig],
    config: Optional[_AppConfig] = None,
    header_comments: Optional[str] = None,
) -> str:
    """Translates a sequences of codes (cells) to a Python file"""
    cell_data: list[Union[CellImpl, tuple[str, CellConfig]]] = []
    defs: set[Name] = set()

    cell_id = 0
    for code, cell_config in zip(codes, cell_configs):
        try:
            cell = compile_cell(code, cell_id=str(cell_id)).configure(
                cell_config
            )
            defs |= cell.defs
            cell_data.append(cell)
        except SyntaxError:
            cell_data.append((code, cell_config))
        cell_id += 1

    unshadowed_builtins = set(builtins.__dict__.keys()) - defs
    fndefs: list[str] = []
    for data, name in zip(cell_data, names):
        if isinstance(data, CellImpl):
            fndefs.append(to_functiondef(data, name, unshadowed_builtins))
        else:
            fndefs.append(
                generate_unparsable_cell(
                    code=data[0], config=data[1], name=name
                )
            )

    filecontents = (
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


class MarimoFileError(Exception):
    pass


def get_app(filename: Optional[str]) -> Optional[App]:
    """Load and return app from a marimo-generated module"""
    if filename is None:
        return None

    with open(filename, "r", encoding="utf-8") as f:
        contents = f.read().strip()

    if not contents:
        return None

    if filename.endswith(".md"):
        from marimo._cli.convert.markdown import convert_from_md_to_app

        return convert_from_md_to_app(contents)

    spec = importlib.util.spec_from_file_location("marimo_app", filename)
    if spec is None:
        raise RuntimeError("Failed to load module spec")
    marimo_app = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load module spec's loader")
    spec.loader.exec_module(marimo_app)
    if not hasattr(marimo_app, "app"):
        raise MarimoFileError(f"{filename} missing attribute `app`.")
    if not isinstance(marimo_app.app, App):
        raise MarimoFileError("`app` attribute must be of type `marimo.App`.")

    app = marimo_app.app
    return app


RECOVERY_CELL_MARKER = "ↁ"


def recover(filename: str) -> str:
    """Generate a module for code recovered from a disconnected frontend"""
    with open(filename, "r", encoding="utf-8") as f:
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
        cast(List[str], codes),
        cast(List[str], names),
        cast(List[CellConfig], configs),
    )


def get_header_comments(filename: str) -> Optional[str]:
    """Gets the header comments from a file. Returns
    None if the file does not exist or the header is
    invalid, which is determined by:
        1. If the file is does not contain the marimo
            import statement
        2. If the section before the marimo import
            statement contains any non-comment code
    """

    def is_multiline_comment(node: ast.stmt) -> bool:
        """Checks if a node is a docstring or a multiline comment."""
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return True
        return False

    if not os.path.exists(filename):
        return None

    with open(filename, "r", encoding="utf-8") as f:
        contents = f.read()

    if "import marimo" not in contents:
        return None

    header, _ = contents.split("import marimo", 1)

    # Ensure the header only contains non-executable code
    # ast parses out single line comments, so we only
    # need to check that every node is not a multiline comment
    module = ast.parse(header)
    if any(not is_multiline_comment(node) for node in module.body):
        return None

    return header
