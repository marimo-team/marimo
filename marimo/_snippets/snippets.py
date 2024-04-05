import os
from dataclasses import dataclass
from typing import Any, Generator, List, Optional

from marimo._ast.codegen import get_app
from marimo._utils.paths import import_files


@dataclass
class SnippetSection:
    html: Optional[str] = None
    code: Optional[str] = None


@dataclass
class Snippet:
    title: str
    sections: List[SnippetSection]


@dataclass
class Snippets:
    snippets: List[Snippet]


def read_snippets():
    snippets: List[Snippet] = []

    for file in snippet_files():
        app = get_app(file)
        sections: List[SnippetSection] = []
        title = ""

        for cell in app._cell_manager.cells():
            code = cell._cell.code
            if should_ignore_code(code):
                continue

            if is_markdown(code):
                if not title and "# " in code:
                    title = get_title_from_code(code)

                output, _defs = cell.run()
                sections.append(SnippetSection(html=output.text))
            else:
                sections.append(SnippetSection(code=code))

        snippets.append(Snippet(title=title, sections=sections))

    return Snippets(snippets=snippets)


def should_ignore_code(code: str) -> bool:
    return code == "import marimo as mo"


def get_title_from_code(code: str) -> str:
    if not code:
        return ""
    if "# " in code:
        # title is the start of # and end of \n
        start = code.find("#")
        end = code[start:].find("\n")
        return code[start:end].strip()
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
