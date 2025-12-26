# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from markdown import (  # type: ignore
    Extension,
    Markdown,
    preprocessors,
    treeprocessors,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


class BreaklessListsPreprocessor(preprocessors.Preprocessor):  # type: ignore[misc]
    """
    Enables CommonMark-style list interruption of paragraphs.

    In CommonMark, lists can interrupt paragraphs without requiring a blank line.
    Python-Markdown requires blank lines, so this preprocessor adds them automatically
    when it detects a list immediately following a paragraph.
    """

    # Pattern to match lines that start list items (ordered or unordered)
    LIST_START_PATTERN = re.compile(r"^(\s*)([*+-]|\d+\.)(\s+)", re.MULTILINE)

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)

    def run(self, lines: list[str]) -> list[str]:
        """Process the lines and insert blank lines before lists that follow paragraphs."""
        if not lines:
            return lines

        result_lines: list[str] = []
        i = 0

        while i < len(lines):
            current_line = lines[i]
            result_lines.append(current_line)

            # Check if we need to look ahead for a list
            if i + 1 < len(lines):
                next_line = lines[i + 1]

                # If current line is not empty and next line starts a list
                if (
                    current_line.strip()  # Current line has content
                    and self.LIST_START_PATTERN.match(next_line)
                ):  # Next line starts a list
                    # Check if there's already a blank line
                    if current_line.strip():
                        # Insert blank line to enable list interruption
                        result_lines.append("")

            i += 1

        return result_lines


class BreaklessListsTreeProcessor(treeprocessors.Treeprocessor):  # type: ignore[misc]
    """
    Removes paragraph tags from list items to create compact lists.

    This makes lists more compact by removing <p> tags within <li> elements.
    """

    def run(self, root: Element) -> None:
        def is_only_child(parent: Element, child: Element) -> bool:
            return len(parent) == 1 and parent[0] is child

        for element in root.iter(tag="li"):
            for p in element.findall(".//p"):
                # If paragraph has no attributes and is the only child
                if not p.attrib and is_only_child(element, p):
                    # Swap the paragraph with the list item
                    element.text = p.text
                    element.tail = p.tail
                    # Copy over the children
                    for child in p:
                        element.append(child)
                    # Remove the paragraph tag
                    element.remove(p)


class BreaklessListsExtension(Extension):  # type: ignore[misc]
    """
    Extension to enable CommonMark-style list interruption of paragraphs.

    This allows lists to follow paragraphs without requiring blank lines,
    matching CommonMark specification behavior. Also makes lists compact
    by removing paragraph tags within list items.
    """

    def extendMarkdown(self, md: Markdown) -> None:
        # Register preprocessor to enable list interruption
        md.preprocessors.register(
            BreaklessListsPreprocessor(md),
            "breakless_lists_preproc",
            # Run early in preprocessing, before other processors
            30,
        )

        # Register tree processor to make lists compact
        md.treeprocessors.register(
            BreaklessListsTreeProcessor(md),
            "breakless_lists_tree",
            # Run after lists are parsed but before paragraph cleanup
            10,
        )
