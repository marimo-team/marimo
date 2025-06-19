# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

from marimo._server.models.packages import DependencyTreeNode
from marimo._utils.uv import find_uv_bin


def parse_name_version(content: str) -> tuple[str, str | None]:
    if " v" in content:
        name, version = content.split(" v", 1)
        return name.strip(), version.split()[0]  # Take only version part
    return content.strip(), None


def parse_uv_tree(text: str) -> DependencyTreeNode:
    """The text output of `uv tree` into a nested data structure."""
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

        # Check for cycle indicator
        is_cycle = content.endswith("(*)")
        if is_cycle:
            content = content[:-3].strip()

        # tags (extras/groups)
        tags: list[dict[str, str]] = []
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
            tags.append({"kind": kind, "value": value.strip()})
            content = content[:start].strip()

        name, version = parse_name_version(content)

        # Add cycle indicator as a special tag
        if is_cycle:
            tags.append({"kind": "cycle", "value": "true"})

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


def get_dependency_tree(filename: str) -> DependencyTreeNode:
    result = subprocess.run(
        [find_uv_bin(), "tree", "--no-dedupe", "--script", filename],
        capture_output=True,
        text=True,
        check=True,
    )
    tree = parse_uv_tree(result.stdout)
    return tree
