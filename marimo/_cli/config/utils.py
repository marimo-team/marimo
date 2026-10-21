# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from msgspec import NODEFAULT, UNSET, Meta, UnsetType
from msgspec.structs import fields

from marimo._cli.print import cyan, green, muted, orange, yellow
from marimo._config.schema_utils import Config


def highlight_toml_headers(toml_string: str) -> str:
    lines = toml_string.splitlines()
    highlighted_lines: list[str] = []

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            highlighted_lines.append(orange(line))
        else:
            highlighted_lines.append(line)

    return "\n".join(highlighted_lines)


def _format_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _format_type(args[0])
    if origin in (Union, types.UnionType):
        return " | ".join(
            _format_type(arg) for arg in args if arg is not UnsetType
        )
    if origin is Literal:
        return "Literal[" + ", ".join(repr(arg) for arg in args) + "]"
    if origin is not None:
        return f"{origin.__name__}[{', '.join(_format_type(arg) for arg in args)}]"
    if annotation is type(None):
        return "None"
    return getattr(annotation, "__name__", str(annotation))


def format_config_docs(cls: type[Config]) -> str:
    """Describe schema fields without loading config or dynamic defaults."""
    output: list[str] = []
    if doc := inspect.getdoc(cls):
        output.extend([muted(f"# {doc}"), ""])

    def format_fields(cls: type[Config], path: str, level: int) -> None:
        prefix = "  " * level
        for item in fields(cls):
            annotation = item.type
            metadata = Meta()
            if get_origin(annotation) is Annotated:
                annotation, *extras = get_args(annotation)
                metadata = next(
                    (extra for extra in extras if isinstance(extra, Meta)),
                    metadata,
                )
            variants = (
                get_args(annotation)
                if get_origin(annotation) in (Union, types.UnionType)
                else (annotation,)
            )
            present = [arg for arg in variants if arg is not UnsetType]
            nested = present[0] if len(present) == 1 else None
            field_path = (
                f"{path}.{item.encode_name}" if path else item.encode_name
            )
            section = (
                nested
                if isinstance(nested, type) and issubclass(nested, Config)
                else None
            )
            extra = metadata.extra or {}
            label = ""
            if extra.get("deprecated"):
                label += orange("[Deprecated] ")
            if extra.get("sensitive"):
                label += cyan("[Sensitive] ")
            if section is not None:
                output.append(f"{prefix}{label}[{green(field_path)}]")
            else:
                output.append(
                    f"{prefix}{label}{yellow(item.encode_name)}: {_format_type(annotation)}"
                )
            if metadata.description:
                output.extend(
                    prefix + muted(f"# {line}")
                    for line in metadata.description.splitlines()
                )
            if section is not None:
                output.append("")
                format_fields(section, field_path, level + 1)
            else:
                if item.default is UNSET:
                    output.append("")
                    continue
                elif item.default is not NODEFAULT:
                    default = repr(item.default)
                elif item.default_factory in (dict, list):
                    default = repr(item.default_factory())
                elif item.default_factory is not NODEFAULT:
                    default = "dynamic"
                else:
                    output.extend([prefix + muted("# Required"), ""])
                    continue
                output.extend([prefix + muted(f"# Default: {default}"), ""])

    format_fields(cls, "", 0)
    return "\n".join(output).rstrip()
