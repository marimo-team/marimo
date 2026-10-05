# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from collections.abc import Callable


class DependencyTag(msgspec.Struct, rename="camel"):
    kind: str
    value: str


class DependencyTreeNode(msgspec.Struct, rename="camel"):
    name: str
    version: str | None
    # List of {"kind": "extra"|"group"|"dedupe"|"cycle", "value": str}
    tags: list[DependencyTag]
    dependencies: list[DependencyTreeNode]


def parse_name_version(content: str) -> tuple[str, str | None]:
    """Parse package name and version from uv tree output."""
    if " v" in content:
        name, version = content.split(" v", 1)
        return name.strip(), version.split()[0]  # Take only version part
    return content.strip(), None


def parse_uv_tree(text: str) -> DependencyTreeNode:
    """Parse the text output of `uv tree` into a nested data structure."""
    # uv emits one footer for all `(*)` markers. With `--no-dedupe`, only
    # cycles are marked; without it, markers mean the subtree was displayed.
    marker_kind = "cycle" if "Package tree is a cycle" in text else "dedupe"
    return _parse_tree(
        text,
        parse_name_version=parse_name_version,
        marker_kind=marker_kind,
    )


def parse_pixi_tree(text: str) -> DependencyTreeNode:
    """Parse `pixi tree` output, where `(*)` means already displayed."""

    def parse_name_version(content: str) -> tuple[str, str | None]:
        parts = content.rsplit(maxsplit=1)
        if len(parts) == 1:
            return parts[0], None
        name, version = parts
        return name, None if version == "<unknown>" else version

    return _parse_tree(
        text,
        parse_name_version=parse_name_version,
        marker_kind="dedupe",
        skip_line=lambda line: line.startswith("Installed for:"),
    )


def _parse_tree(
    text: str,
    *,
    parse_name_version: Callable[[str], tuple[str, str | None]],
    marker_kind: str,
    skip_line: Callable[[str], bool] | None = None,
) -> DependencyTreeNode:
    lines = text.strip().split("\n")

    # Create a virtual root to hold all top-level dependencies
    tree = DependencyTreeNode(
        name="<root>", version=None, tags=[], dependencies=[]
    )
    stack = [(tree, -1)]  # (node, level)

    for line in lines:
        line = line.rstrip()
        if (
            not line
            or "Package tree already displayed" in line
            or "Package tree is a cycle" in line
            or (skip_line is not None and skip_line(line))
        ):
            continue

        # Calculate indentation level by counting characters before tree symbols
        if not any(symbol in line for symbol in ["├──", "└──"]):
            level = 0  # Top-level package
        else:
            # Find the tree symbol position and divide by 4 (standard tree indentation)
            for symbol in ["├──", "└──"]:
                pos = line.find(symbol)
                if pos != -1:
                    level = (pos // 4) + 1
                    break

        # content after tree symbols
        content = line.lstrip("│ ├└─").strip()

        is_repeated = content.endswith("(*)")
        if is_repeated:
            content = content[:-3].strip()

        # tags (extras/groups)
        tags: list[DependencyTag] = []

        while "(extra:" in content or "(group:" in content:
            start = (
                content.rfind("(extra:")
                if "(extra:" in content
                else content.rfind("(group:")
            )
            if start == -1:
                break
            end = content.find(")", start)
            if end == -1:
                break
            tag_text = content[start + 1 : end]
            kind, value = tag_text.split(":", 1)
            assert kind == "extra" or kind == "group"
            tags.append(DependencyTag(kind=kind, value=value.strip()))
            content = content[:start].strip()

        name, version = parse_name_version(content)

        if is_repeated:
            tags.append(DependencyTag(kind=marker_kind, value="true"))

        node = DependencyTreeNode(
            name=name,
            version=version,
            tags=tags,
            dependencies=[],
        )

        # Adjust stack to correct level
        while len(stack) > 1 and stack[-1][1] >= level:
            stack.pop()

        # Add to parent and push to stack
        stack[-1][0].dependencies.append(node)
        stack.append((node, level))

    return tree
