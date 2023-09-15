# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import builtins
import importlib.util
import json
from collections.abc import Sequence
from typing import Any, Optional, Union

from marimo import __version__
from marimo._ast.app import App, _AppConfig
from marimo._ast.cell import Cell, CellConfig, parse_cell
from marimo._ast.visitor import Name

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
    if config is None or config == CellConfig():
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
    cell: Cell, name: str, unshadowed_builtins: Optional[set[Name]] = None
) -> str:
    # unshadowed builtins is the set of builtins that haven't been
    # overriden (shadowed) by other cells in the app. These names
    # should not be taken as args by a cell's functiondef (since they are
    # already in globals)
    if unshadowed_builtins is None:
        unshadowed_builtins = set(builtins.__dict__.keys())
    refs = [ref for ref in sorted(cell.refs) if ref not in unshadowed_builtins]
    args = ", ".join(refs)

    decorator = _to_decorator(cell.config)
    signature = f"def {name}({args}):"
    if len(INDENT + signature) >= MAX_LINE_LENGTH:
        signature = f"def {name}{_multiline_tuple(refs)}:"
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


def generate_unparseable_cell(
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
) -> str:
    """Translates a sequences of codes (cells) to a Python file"""
    cell_function_data: list[Union[Cell, tuple[str, CellConfig]]] = []
    defs: set[Name] = set()

    for code, cell_config in zip(codes, cell_configs):
        try:
            cell = parse_cell(code).configure(cell_config)
            defs |= cell.defs
            cell_function_data.append(cell)
        except SyntaxError:
            cell_function_data.append((code, cell_config))

    unshadowed_builtins = set(builtins.__dict__.keys()) - defs
    fndefs: list[str] = []
    for data, name in zip(cell_function_data, names):
        if isinstance(data, Cell):
            fndefs.append(to_functiondef(data, name, unshadowed_builtins))
        else:
            fndefs.append(
                generate_unparseable_cell(
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
    app._validate_args()
    return app


RECOVERY_CELL_MARKER = "ↁ"


def recover(filename: str) -> str:
    """Generate a module for code recovered from a disconnected frontend"""
    with open(filename, "r") as f:
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
    return generate_filecontents(codes, names, configs)
