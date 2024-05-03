# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any, Callable, Literal

# Native to python
from xml.etree.ElementTree import Element, SubElement

# Note: yaml is also a python builtin
import yaml

# Markdown is a dependency of marimo, as such we utilize it as much as possible
# to parse markdown.
from markdown import Markdown
from markdown.blockparser import BlockParser
from markdown.blockprocessors import BlockProcessor
from markdown.preprocessors import Preprocessor
from markdown.util import HTML_PLACEHOLDER_RE, Registry

# As are extensions
from pymdownx.superfences import SuperFencesCodeExtension  # type: ignore

from marimo._ast.app import _AppConfig
from marimo._cli.convert.utils import generate_from_sources, markdown_to_marimo

# CSafeLoader is faster than SafeLoader.
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader  # type: ignore[assignment]

MARIMO_MD = "marimo-md"
MARIMO_CODE = "marimo-code"


def _is_code_tag(text: str) -> bool:
    head = text.split("\n")[0].strip()
    return bool(re.search(r"\{.*marimo.*\}", head))


def _tree_to_app(root: Element) -> str:
    # Extract meta data from root attributes.
    config_keys = {"title": "app_title"}
    config = {
        config_keys[key]: value
        for key, value in root.items()
        if key in config_keys
    }
    app_config = _AppConfig.from_untrusted_dict(config)

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

    return generate_from_sources(sources, app_config)


class MarimoParser(Markdown):
    """Parses Markdown to marimo notebook."""

    # Considering how ubiquitous "markdown" is, it's a little surprising the
    # internal structure isn't cleaner/ more modular. This "monkey-patching"
    # is comparable to some of the code in markdown extensions- and given this
    # library has been around since 2004, the internals should be relatively
    # stable.
    output_formats: dict[Literal["marimo"], Callable[[Element], str]] = {  # type: ignore[assignment, misc]
        "marimo": _tree_to_app,
    }
    meta: dict[str, Any]

    def build_parser(self) -> MarimoParser:
        """
        Creates blank registries as a base.

        Note that evoked by itself, will create an infinite loop, since
        block-parsers will never dequeue the extracted blocks.
        """
        self.preprocessors = Registry()
        self.parser = BlockParser(self)
        self.inlinePatterns = Registry()
        self.treeprocessors = Registry()
        self.postprocessors = Registry()
        return self


class FrontMatterPreprocessor(Preprocessor):
    """Preprocessor for to extract YAML front matter.

    The built-in MetaPreprocessor does not handle frontmatter yaml properly, so
    this is a custom implementation.

    Like the built-in MetaPreprocessor, this preprocessor extracts yaml and
    stores it in the Markdown's metadata attribute. Inspired by conversation
    and linked project in github/Python-Markdown/markdown/497. See docdown
    (BSD-3) or python-frontmatter (MIT) for similar implementations.
    """

    def __init__(self, md: MarimoParser):
        super().__init__(md)
        self.md = md
        self.md.meta = {}
        # Regex captures loose yaml for frontmatter
        # Should match the following:
        # ---
        # title: "Title"
        # whatever
        # ---
        self.yaml_front_matter_regex = re.compile(
            r"^---\s*\n(.*?\n?)(?:---)\s*\n", re.UNICODE | re.DOTALL
        )

    def run(self, lines: list[str]) -> list[str]:
        if not lines:
            return lines

        doc = "\n".join(lines)
        result = self.yaml_front_matter_regex.match(doc)

        if result:
            yaml_content = result.group(1)
            try:
                meta = yaml.load(yaml_content, SafeLoader)
                if isinstance(meta, dict):
                    self.md.meta = meta  # type: ignore[attr-defined]
                doc = doc[result.end() :].lstrip("\n")
            # If there's an error in parsing YAML, ignore the meta and proceed.
            except yaml.YAMLError as e:
                raise e
        return doc.split("\n")


class ExpandAndClassifyProcessor(BlockProcessor):
    """Separates code blocks and markdown blocks."""

    stash: dict[str, Any]

    def test(*_args: Any) -> bool:
        return True

    def run(self, parent: Element, blocks: list[str]) -> None:
        # Copy app metadata to the parent element.
        for key, value in self.parser.md.meta.items():  # type: ignore[attr-defined]
            if isinstance(value, str):
                parent.set(key, value)

        text: list[str] = []

        def add_paragraph() -> None:
            if not text:
                return
            # An additional line break is added before code blocks.
            if text[-1].strip() == "":
                text.pop()
                if not text:
                    return
            paragraph = SubElement(parent, MARIMO_MD)
            paragraph.text = "\n".join(text).strip()
            text.clear()

        # Operate on line basis, not block basis, but use block processor
        # instead of preprocessor, because we still want to operate on the
        # xml tree.
        for line in "\n\n".join(blocks).split("\n"):
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
    md.preprocessors.register(FrontMatterPreprocessor(md), "frontmatter", 100)
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
    if not text:
        raise ValueError("No content found in markdown.")
    md = _build_marimo_parser()
    return md.convert(text)
