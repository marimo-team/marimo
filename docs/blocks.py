import textwrap
import xml.etree.ElementTree as etree
from typing import Any, Dict, List, Union, cast
import urllib.parse

from pymdownx.blocks import BlocksExtension  # type: ignore
from pymdownx.blocks.block import Block, type_string_in  # type: ignore


class MarimoEmbedBlock(Block):
    NAME: str = "marimo-embed"
    OPTIONS: Dict[str, List[Union[str, Any]]] = {
        "size": ["medium", type_string_in(["small", "medium", "large"])],
        "app_width": ["wide", type_string_in(["wide", "full", "compact"])],
        "mode": ["read", type_string_in(["read", "edit"])],
    }

    def on_create(self, parent: etree.Element) -> etree.Element:
        # Create container div
        container = etree.SubElement(parent, "div")
        container.set("class", "marimo-embed-container")
        return container

    def on_add(self, block: etree.Element) -> etree.Element:
        return block

    def on_end(self, block: etree.Element) -> None:
        # Extract the Python code
        code = block.text.strip() if block.text else ""

        # Remove ```python if present
        if code.startswith("```python"):
            code = code[9:]  # first 9 characters are ```python
            code = code[:-3]  # last 3 characters are ```

        # Dedent the code
        code = textwrap.dedent(code)

        # Create iframe element
        size: str = cast(str, self.options["size"])
        app_width: str = cast(str, self.options["app_width"])
        mode: str = cast(str, self.options["mode"])
        url = create_marimo_iframe(code=code, app_width=app_width, mode=mode)

        # Clear existing content
        block.text = None
        for child in block:
            block.remove(child)

        # Add iframe
        iframe = etree.SubElement(block, "iframe")
        iframe.set("class", f"demo {size}")
        iframe.set("src", url)
        iframe.set(
            "allow",
            "camera; geolocation; microphone; fullscreen; autoplay; encrypted-media; picture-in-picture; clipboard-read; clipboard-write",
        )
        iframe.set("width", "100%")
        iframe.set("height", "400px")
        iframe.set("frameborder", "0")
        iframe.set("style", "display: block; margin: 0 auto;")

    def on_markdown(self) -> str:
        return "raw"


def uri_encode_component(code: str) -> str:
    return urllib.parse.quote(code, safe="~()*!.'")


def create_marimo_iframe(
    *,
    code: str,
    mode: str = "read",
    app_width: str = "wide",
) -> str:
    header = "\n".join(
        [
            "import marimo",
            f'app = marimo.App(width="{app_width}")',
            "",
        ]
    )
    footer = "\n".join(
        [
            "",
            "@app.cell",
            "def __():",
            "    import marimo as mo",
            "    return",
        ]
    )
    body = header + code + footer
    encoded_code = uri_encode_component(body)
    return f"https://marimo.app/?code={encoded_code}&embed=true&mode={mode}"


class MarimoBlocksExtension(BlocksExtension):
    def extendMarkdownBlocks(self, md: Any, block_mgr: Any) -> None:
        block_mgr.register(MarimoEmbedBlock, self.getConfigs())


def makeExtension(*args: Any, **kwargs: Any) -> MarimoBlocksExtension:
    return MarimoBlocksExtension(*args, **kwargs)
