# Copyright 2024 Marimo. All rights reserved.
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Generator, List, Optional

from marimo._ast.codegen import get_app
from marimo._utils.paths import import_files


@dataclass
class SnippetSection:
    id: str
    html: Optional[str] = None
    code: Optional[str] = None


@dataclass
class Snippet:
    title: str
    sections: List[SnippetSection]


@dataclass
class Snippets:
    snippets: List[Snippet]


async def read_snippets() -> Snippets:
    snippets: List[Snippet] = []

    for file in snippet_files():
        app = get_app(file)
        assert app is not None
        sections: List[SnippetSection] = []
        title = ""

        for cell in app._cell_manager.cells():
            if not cell:
                continue

            code = cell._cell.code
            if should_ignore_code(code):
                continue

            if is_markdown(code):
                if not title and "# " in code:
                    title = get_title_from_code(code)

                ret = cell.run()
                if isinstance(ret, Awaitable):
                    output, _defs = await ret
                else:
                    output, _defs = ret
                sections.append(
                    SnippetSection(html=output.text, id=cell._cell.cell_id)
                )
            else:
                sections.append(
                    SnippetSection(code=code, id=cell._cell.cell_id)
                )

        snippets.append(Snippet(title=title, sections=sections))

    return Snippets(
        snippets=sorted(snippets, key=lambda snippet: snippet.title)
    )


def should_ignore_code(code: str) -> bool:
    return code == "import marimo as mo"


def get_title_from_code(code: str) -> str:
    if not code:
        return ""
    if "# " in code:
        # title is the start of # and end of \n
        start = code.find("#")
        end = code[start:].find("\n")
        return code[start : end + start].replace("#", "", 1).strip()
    return ""


def is_markdown(code: str) -> bool:
    return code.startswith("mo.md")


def snippet_files() -> Generator[str, Any, None]:
    root = os.path.realpath(
        str(import_files("marimo").joinpath("_snippets").joinpath("data"))
    )
    for _root, _dirs, files in os.walk(root):
        for file in files:
            if file.endswith(".py"):
                yield os.path.join(root, file)
