# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Literal

# Native to python
from xml.etree.ElementTree import Element, SubElement

# Markdown is a dependency of marimo, as such we utilize it as much as possible
# to parse markdown.
from markdown import Markdown
from markdown.blockparser import BlockParser
from markdown.blockprocessors import BlockProcessor
from markdown.extensions.meta import MetaPreprocessor
from markdown.util import HTML_PLACEHOLDER_RE, Registry

# As are extensions
from pymdownx.superfences import SuperFencesCodeExtension  # type: ignore

from marimo._cli.convert.utils import generate_from_sources, markdown_to_marimo

MARIMO_MD = "marimo-md"
MARIMO_CODE = "marimo-code"


def _is_code_tag(text: str) -> bool:
    head = text.split("\n")[0].strip()
    return head.endswith("{marimo}")


def _tree_to_app(root: Element) -> str:
    sources = []
    for child in root:
        source = child.text
        if not (source and source.strip()):
            continue
        if child.tag == MARIMO_MD:
            source = markdown_to_marimo(source)
        else:
            assert child.tag == MARIMO_CODE, f"Unknown tag: {child.tag}"
        sources.append(source)

    return generate_from_sources(sources)


class MarimoParser(Markdown):
    """Parses Markdown to marimo notebook."""

    # Considering how ubiquitous "markdown" is, it's a little suprising the
    # internal structure isn't cleaner/ more modular. This "monkey-patching"
    # is comparable to some of the code in markdown extensions- and given this
    # library has been around since 2004, the internals should be relatively
    # stable.
    output_formats: dict[Literal["marimo"], Callable[[Element], str]] = {  # type: ignore[assignment, misc]
        "marimo": _tree_to_app,
    }

    def build_parser(self) -> MarimoParser:
        """
        Creates blank registries as a base.

        Note that envoked by itself, will create an infinite loop, since
        block-parsers will never dequeue the extracted blocks.
        """
        self.preprocessors = Registry()
        self.parser = BlockParser(self)
        self.inlinePatterns = Registry()
        self.treeprocessors = Registry()
        self.postprocessors = Registry()
        return self


class ExpandAndClassifyProcessor(BlockProcessor):
    """Seperates code blocks and markdown blocks."""

    stash: dict[str, Any]
    yaml_meta: bool

    def test(*_args: Any) -> bool:
        return True

    def run(self, parent: Element, blocks: list[str]) -> None:
        text: list[str] = []
        self.yaml_meta = True

        def add_paragraph() -> None:
            # On first markdown block, check if it contains yaml
            # (or partially parsed yaml).
            if self.yaml_meta:
                self.yaml_meta = False
                if text[-1] == "---":
                    text.clear()
                    return
            if text:
                paragraph = SubElement(parent, MARIMO_MD)
                paragraph.text = "\n".join(text)
                text.clear()

        # Operate on line basis, not block basis, but use block processor
        # instead of preprocessor, because we still want to operate on the
        # xml tree.
        for line in "\n".join(blocks).split("\n"):
            # Superfences replaces code blocks with a placeholder,
            # Check for the placeholder, and ensure it is a marimo code block,
            # otherwise consider it as markdown.
            if HTML_PLACEHOLDER_RE.match(line.strip()):
                lookup = line.strip()[1:-1]
                code = self.stash[lookup][0]
                if _is_code_tag(code):
                    add_paragraph()
                    code_block = SubElement(parent, MARIMO_CODE)
                    code_block.text = "\n".join(code.split("\n")[1:-1])
                    # If code block, then it cannot be the initial yaml.
                    self.yaml_meta = False
                else:
                    text.extend(code.split("\n"))
            else:
                text.append(line)
        add_paragraph()
        # Flush to indicate all blocks have been processed.
        blocks.clear()


def _build_marimo_parser() -> MarimoParser:
    # Build here opposed to the parent class since there is intermediate logic
    # after the parser is built, and it is more clear here what is registered.
    md = MarimoParser(output_format="marimo")  # type: ignore[arg-type]
    md.stripTopLevelTags = False

    # Note: MetaPreprocessor does not properly handle frontmatter yaml, so
    # cleanup occurs in the block-processor.
    md.preprocessors.register(MetaPreprocessor(md), "meta", 100)
    fences_ext = SuperFencesCodeExtension()
    fences_ext.extendMarkdown(md)
    # TODO: Consider adding the admonition extension, and integrating it with
    # mo.markdown callouts.

    block_processors = ExpandAndClassifyProcessor(md.parser)
    block_processors.stash = fences_ext.stash.stash
    md.parser.blockprocessors.register(
        block_processors, "marimo-processor", 10
    )

    return md


def convert_from_md(text: str) -> str:
    md = _build_marimo_parser()
    return md.convert(text)
