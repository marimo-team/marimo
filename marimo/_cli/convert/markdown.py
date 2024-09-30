# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, Union

# Native to python
from xml.etree.ElementTree import Element, SubElement

# Markdown is a dependency of marimo, as such we utilize it as much as possible
# to parse markdown.
from markdown import Markdown
from markdown.blockparser import BlockParser
from markdown.blockprocessors import BlockProcessor
from markdown.preprocessors import Preprocessor
from markdown.util import HTML_PLACEHOLDER_RE, Registry

# As are extensions
from pymdownx.superfences import (  # type: ignore
    RE_NESTED_FENCE_START,
    SuperFencesCodeExtension,
)

from marimo._ast import codegen
from marimo._ast.app import App, InternalApp, _AppConfig
from marimo._ast.cell import Cell, CellConfig
from marimo._ast.compiler import compile_cell
from marimo._convert.utils import markdown_to_marimo

MARIMO_MD = "marimo-md"
MARIMO_CODE = "marimo-code"

ConvertKeys = Union[Literal["marimo"], Literal["marimo-app"]]


def _is_code_tag(text: str) -> bool:
    head = text.split("\n")[0].strip()
    return bool(re.search(r"\{.*python.*\}", head))


def formatted_code_block(
    code: str, attributes: Optional[dict[str, str]] = None
) -> str:
    """Wraps code in a fenced code block with marimo attributes."""
    if attributes is None:
        attributes = {}
    attribute_str = " ".join(
        [""] + [f'{key}="{value}"' for key, value in attributes.items()]
    )
    guard = "```"
    while guard in code:
        guard += "`"
    return "\n".join(
        [f"""{guard}{{.python.marimo{attribute_str}}}""", code, guard, ""]
    )


def app_config_from_root(root: Element) -> _AppConfig:
    # Extract meta data from root attributes.
    config_keys = {
        "title": "app_title",
    }
    config = {
        config_keys[key]: value
        for key, value in root.items()
        if key in config_keys
    }
    # Try to pass on other attributes as is
    config.update({k: v for k, v in root.items() if k not in config_keys})
    # Remove values particular to markdown saves.
    config.pop("marimo-version", None)

    return _AppConfig.from_untrusted_dict(config)


def get_source_from_tag(tag: Element) -> str:
    source = tag.text if tag.text else ""
    if tag.tag == MARIMO_MD:
        # Only check here to allow for empty code blocks.
        if not (source and source.strip()):
            return ""
        source = markdown_to_marimo(source)
    else:
        assert tag.tag == MARIMO_CODE, f"Unknown tag: {tag.tag}"
    return source


def get_cell_config_from_tag(tag: Element, **defaults: bool) -> CellConfig:
    boolean_attrs = {
        **defaults,
        **{k: v == "true" for k, v in tag.attrib.items()},
    }
    return CellConfig.from_dict(boolean_attrs)


# TODO: Consider upstreaming some logic such that this isn't such a terrible
# hack. At some point rewriting / overriding the markdown parser would be a
# better idea than all these little work arounds.
@dataclass
class SafeWrap:
    app: App

    def strip(self) -> App:
        return self.app


def _tree_to_app_obj(root: Element) -> SafeWrap:
    app_config = app_config_from_root(root)
    app = InternalApp(App(**app_config.asdict()))

    for child in root:
        name = child.get("name", "__")
        # Default to hiding markdown cells.
        cell_config = get_cell_config_from_tag(
            child, hide_code=child.tag == MARIMO_MD
        )
        source = get_source_from_tag(child)

        cell_id = app.cell_manager.create_cell_id()
        try:
            cell_impl = compile_cell(source, cell_id)
            cell_impl.configure(cell_config)
            cell = Cell(_name=name, _cell=cell_impl)

            app.cell_manager._register_cell(
                cell,
                app=app,
            )
        except SyntaxError:
            # Cannot use register_unparsable_cell, since there is an
            # expectation of a dedent and newlines.
            app.cell_manager.register_cell(
                cell_id=cell_id,
                code=source,
                config=cell_config,
                name=name or "__",
                cell=None,
            )

    return SafeWrap(app._app)


def _tree_to_app(root: Element) -> str:
    app_config = app_config_from_root(root)

    sources: list[str] = []
    names: list[str] = []
    cell_config: list[CellConfig] = []
    for child in root:
        names.append(child.get("name", "__"))
        cell_config.append(get_cell_config_from_tag(child))
        sources.append(get_source_from_tag(child))

    return codegen.generate_filecontents(
        sources,
        names,
        cell_config,
        config=app_config,
    )


class IdentityParser(Markdown):
    """Leaves markdown unchanged."""

    # Considering how ubiquitous "markdown" is, it's a little surprising the
    # internal structure isn't cleaner/ more modular. This "monkey-patching"
    # is comparable to some of the code in markdown extensions- and given this
    # library has been around since 2004, the internals should be relatively
    # stable.
    output_formats: dict[Literal["identity"], Callable[[Element], str]] = {  # type: ignore[assignment, misc]
        "identity": lambda x: x.text if x.text else "",
    }

    def build_parser(self) -> IdentityParser:
        """
        Creates blank registries as a base.
        """
        self.preprocessors = Registry()
        self.parser = BlockParser(self)
        self.inlinePatterns = Registry()
        self.treeprocessors = Registry()
        self.postprocessors = Registry()
        return self

    def convert(self, text: str) -> str:
        """Override the convert method to return the parsed text.

        Note that evoked by itself, would create an infinite loop, since
        block-parsers will never dequeue the extracted blocks.
        """
        if len(self.parser.blockprocessors) == 0:
            self.parser.blockprocessors.register(
                IdentityProcessor(self.parser), "identity", 1
            )

        return super().convert(text)


class MarimoParser(IdentityParser):
    """Parses Markdown to marimo notebook string."""

    meta: dict[str, Any]

    output_formats: dict[ConvertKeys, Callable[[Element], Union[str, App]]] = {  # type: ignore[assignment, misc]
        "marimo": _tree_to_app,
        "marimo-app": _tree_to_app_obj,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Build here opposed to the parent class since there is intermediate
        # logic after the parser is built, and it is more clear here what is
        # registered.
        self.stripTopLevelTags = False

        # Note: MetaPreprocessor does not properly handle frontmatter yaml, so
        # cleanup occurs in the block-processor.
        self.preprocessors.register(
            FrontMatterPreprocessor(self), "frontmatter", 100
        )
        fences_ext = SuperFencesCodeExtension()
        fences_ext.extendMarkdown(self)
        # TODO: Consider adding the admonition extension, and integrating it
        # with mo.markdown callouts.

        block_processor = ExpandAndClassifyProcessor(self.parser)
        block_processor.stash = fences_ext.stash.stash
        self.parser.blockprocessors.register(
            block_processor, "marimo-processor", 10
        )


class SanitizeParser(IdentityParser):
    """Sanitizes Markdown to non-executable string."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Potentially no need for a separate sanitizer. We could use a
        # heuristic to determine if this block should be treated as code, but
        # to catch all edgecases, just run it through the similar superfence
        # logic.
        self.stripTopLevelTags = False

        fences_ext = SuperFencesCodeExtension()
        fences_ext.extendMarkdown(self)

        preprocessor = SanitizeProcessor(self)
        preprocessor.stash = fences_ext.stash.stash
        self.preprocessors.register(preprocessor, "marimo-sanitizer", 1)

        # Add back in identity to dequeue.
        self.parser.blockprocessors.register(
            IdentityProcessor(self.parser), "identity", 1
        )


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
        import yaml

        # CSafeLoader is faster than SafeLoader.
        try:
            from yaml import CSafeLoader as SafeLoader
        except ImportError:
            from yaml import SafeLoader  # type: ignore[assignment]

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


class SanitizeProcessor(Preprocessor):
    """Prevent unintended executable code block injection.

    Typically run on Markdown fragments (e.g. cells) to prevent code injection.
    **Note***: Must run after SuperFencesCodeExtension.
    """

    stash: dict[str, Any]

    def run(self, lines: list[str]) -> list[str]:
        # Note, an empty stash is not sufficient since partially open code
        # blocks could be in the text.
        if not lines:
            return lines

        is_code = False
        for i, line in enumerate(lines):
            # Still need to do all replacements
            if HTML_PLACEHOLDER_RE.match(line.strip()):
                lookup = line.strip()[1:-1]
                code = self.stash[lookup][0]
                lines[i] = code
                # This is a tag we would normally parse on.
                # So protect it from being parsed improperly, by just treating
                # it as code.
                is_code = is_code or _is_code_tag(code)
            # We also need to check for code block delimiters that superfences
            # did not catch, as this will break other code blocks.
            is_code = is_code or RE_NESTED_FENCE_START.match(line)

        if not is_code:
            return lines

        return formatted_code_block(
            markdown_to_marimo("\n".join(lines))
        ).split("\n")


class IdentityProcessor(BlockProcessor):
    """Leaves markdown unchanged."""

    def test(*_args: Any) -> bool:
        return True

    def run(self, parent: Element, blocks: list[str]) -> None:
        parent.text = "\n\n".join(blocks)
        blocks.clear()


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
            if not HTML_PLACEHOLDER_RE.match(line.strip()):
                # Use <!----> to indicate a separation between cells.
                if line.strip() == "<!---->":
                    add_paragraph()
                    continue
                text.append(line)
                continue

            lookup = line.strip()[1:-1]
            code = self.stash[lookup][0]
            if not _is_code_tag(code):
                text.extend(code.split("\n"))
                continue

            # Definitively a code block, so add the previous markdown.
            add_paragraph()

            code_block = SubElement(parent, MARIMO_CODE)
            block_lines = code.split("\n")
            code_block.text = "\n".join(block_lines[1:-1])
            # Extract attributes from the code block.
            # Blocks are expected to be like this:
            # {.python.marimo disabled="true"}
            fence_start = RE_NESTED_FENCE_START.match(block_lines[0])
            if fence_start:
                # attrs is a bit of a misnomer, matches
                # .python.marimo disabled="true"
                inner = fence_start.group("attrs")
                if inner:
                    code_block.attrib = dict(
                        re.findall(r'(\w+)="([^"]*)"', inner)
                    )
        add_paragraph()
        # Flush to indicate all blocks have been processed.
        blocks.clear()


def convert_from_md_to_app(text: str) -> App:
    return MarimoParser(output_format="marimo-app").convert(text)  # type: ignore[arg-type, return-value]


def convert_from_md(text: str) -> str:
    return MarimoParser(output_format="marimo").convert(text)  # type: ignore[arg-type]


def sanitize_markdown(text: str) -> str:
    return SanitizeParser(output_format="identity").convert(text)  # type: ignore[arg-type]


def is_sanitized_markdown(text: str) -> bool:
    # "Unsanitized" markdown contains potentially unintended executatable code
    # block, which require backticks.
    return "```" not in text or sanitize_markdown(text) == text
