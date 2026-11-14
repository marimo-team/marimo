"""Render configuration schema metadata for the documentation build."""

from __future__ import annotations

import re

from msgspec import NODEFAULT, inspect as mi

from marimo._config.config_schema import MarimoConfig


def _unwrap(info: mi.Type) -> mi.Type:
    return _unwrap(info.type) if isinstance(info, mi.Metadata) else info


def _format_type(info: mi.Type) -> str:
    info = _unwrap(info)
    if isinstance(info, mi.UnionType):
        return " | ".join(_format_type(item) for item in info.types)
    if isinstance(info, mi.LiteralType):
        return "Literal[" + ", ".join(repr(v) for v in info.values) + "]"
    if isinstance(info, mi.ListType):
        return f"list[{_format_type(info.item_type)}]"
    if isinstance(info, mi.DictType):
        return f"dict[{_format_type(info.key_type)}, {_format_type(info.value_type)}]"
    if isinstance(info, mi.StructType):
        return "table"
    return {
        mi.AnyType: "Any",
        mi.BoolType: "bool",
        mi.IntType: "int",
        mi.FloatType: "float",
        mi.StrType: "str",
        mi.NoneType: "None",
    }[type(info)]


def _default(field: mi.Field) -> str | None:
    if field.required:
        return "Required"
    if field.default is not NODEFAULT:
        return f"`{field.default!r}`"
    if field.default_factory in (dict, list):
        return f"`{field.default_factory()!r}`"
    if field.default_factory is not NODEFAULT:
        if isinstance(_unwrap(field.type), mi.StructType):
            return "See defaults below."
        return "Dynamic (determined at runtime)."
    return None


def _status_badge(status: str) -> str:
    return (
        f'<span class="configuration-status configuration-{status}">'
        f"{status.capitalize()}</span>"
    )


def _render_fields(
    info: mi.Type,
    path: str,
    level: int,
    *,
    experimental: bool = False,
    deprecated: bool = False,
) -> list[str]:
    info = _unwrap(info)
    if isinstance(info, mi.UnionType):
        return [
            line
            for variant in info.types
            for line in _render_fields(
                variant,
                path,
                level,
                experimental=experimental,
                deprecated=deprecated,
            )
        ]
    if isinstance(info, mi.ListType):
        return _render_fields(
            info.item_type,
            path + "[]",
            level,
            experimental=experimental,
            deprecated=deprecated,
        )
    if isinstance(info, mi.DictType):
        return _render_fields(
            info.value_type,
            path + ".<name>",
            level,
            experimental=experimental,
            deprecated=deprecated,
        )
    if not isinstance(info, mi.StructType):
        return []

    lines: list[str] = []
    # Tagged variants share field paths; distinguish their headings and anchors.
    variant = f" ({info.tag})" if info.tag is not None else ""
    for field in info.fields:
        field_path = (
            f"{path}.{field.encode_name}" if path else field.encode_name
        )
        metadata = field.type if isinstance(field.type, mi.Metadata) else None
        extra = (metadata.extra or {}) if metadata else {}
        schema = (metadata.extra_json_schema or {}) if metadata else {}
        is_experimental = (
            experimental
            or field_path == "experimental"
            or bool(extra.get("experimental"))
        )
        is_deprecated = deprecated or bool(
            extra.get("deprecated") or schema.get("deprecated")
        )
        anchor_path = field_path.replace("[]", ".item") + variant
        anchor = re.sub(r"[^a-z0-9_-]+", "-", anchor_path.lower()).strip("-")
        is_category = not path and level == 2
        if is_category:
            title = field_path.replace("_", " ").capitalize()
            if field_path in ("ai", "mcp"):
                title = field_path.upper()
            heading = f"## {title} {{ #{anchor} .configuration-category }}"
        else:
            heading = (
                f"{'#' * min(level, 6)} `{field_path}`{variant} "
                f"{{ #{anchor} .configuration-option }}"
            )
        lines.extend(
            [
                heading,
                "",
            ]
        )
        labels: list[str] = []
        if is_deprecated:
            labels.append(_status_badge("deprecated"))
        if is_experimental:
            labels.append(_status_badge("experimental"))
        if extra.get("sensitive"):
            labels.append(_status_badge("sensitive"))
        if labels:
            lines.extend([" ".join(labels), ""])
        if description := schema.get("description"):
            lines.extend([description, ""])
        if not is_category:
            lines.extend(
                [
                    f"**Type:** `{_format_type(field.type)}`",
                    "",
                ]
            )
            if default := _default(field):
                lines.extend([f"**Default:** {default}", ""])
        lines.extend(
            _render_fields(
                field.type,
                field_path,
                level + 1,
                experimental=is_experimental,
                deprecated=is_deprecated,
            )
        )
    return lines


def render_config_reference() -> str:
    """Describe every schema field without evaluating configuration factories."""
    return "\n".join(_render_fields(mi.type_info(MarimoConfig), "", 2))
