# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from textwrap import dedent
from typing import TYPE_CHECKING, List, Optional, Union, cast

from marimo import __version__, _loggers
from marimo._ast.app import App, InternalApp, _AppConfig
from marimo._ast.cell import Cell, CellConfig
from marimo._ast.compiler import compile_cell
from marimo._messaging.cell_output import CellOutput
from marimo._output.formatting import as_html, mime_to_html
from marimo._output.utils import uri_encode_component
from marimo._plugins.ui import code_editor
from marimo._server.export import run_app_until_completion
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from marimo._server.session.session_view import SessionView

LOGGER = _loggers.marimo_logger()


class MarimoIslandStub:
    def __init__(
        self,
        display_code: bool = False,
        display_output: bool = True,
        is_reactive: bool = True,
        *,
        cell_id: str,
        app_id: str,
        code: str,
    ):
        self._cell_id = cell_id
        self._app_id = app_id
        self._code = code
        self._display_code = display_code
        self._display_output = display_output
        self._is_reactive = is_reactive

        self._internal_app: Optional[InternalApp] = None
        self._session_view: Optional[SessionView] = None
        self._output: Optional[CellOutput] = None

    @property
    def output(self) -> Optional[CellOutput]:
        # Leave output accessible for direct use for non-interactive cases e.g.
        # pdf.
        if self._output is None:
            if self._session_view is not None:
                outputs = self._session_view.get_cell_outputs([self._cell_id])
                self._output = outputs.get(self._cell_id, None)
        return self._output

    @property
    def code(self) -> str:
        return self._code

    def render(
        self,
        display_code: Optional[bool] = None,
        display_output: Optional[bool] = None,
        is_reactive: Optional[bool] = None,
    ) -> str:
        """
        Render the HTML island code for the cell.
        Note: This will override construction defaults.

        *Args:*

        - display_code (bool): Whether to display the code in HTML.
        - display_output (bool): Whether to include the output in the HTML.
        - is_reactive (bool): Whether this code block will run with pyodide.

        *Returns:*

        - str: The HTML code.
        """

        is_reactive = (
            is_reactive if is_reactive is not None else self._is_reactive
        )
        display_code = (
            display_code if display_code is not None else self._display_code
        )
        display_output = (
            display_output
            if display_output is not None
            else self._display_output
        )

        if not (display_code or display_output or is_reactive):
            raise ValueError("You must include either code or output")

        output = (
            mime_to_html(self.output.mimetype, self.output.data)
            if self.output is not None
            else None
        )

        # Specifying display_code=False will hide the code block, but still
        # make it present for reactivity, unless reactivity is disabled.
        if display_code:
            # TODO: Allow for non-disabled code editors.
            code_block = as_html(code_editor(self.code, disabled=False)).text
        else:
            code_block = (
                "<marimo-cell-code hidden>"
                f"{uri_encode_component(self.code) if is_reactive else ''}"
                "</marimo-cell-code>"
            )

        # Cell may not have output
        # (e.g. imports, but still needs to be included)
        return remove_empty_lines(
            dedent(
                f"""
        <marimo-island
            data-app-id="{self._app_id}"
            data-cell-id="{self._cell_id}"
            data-reactive="{json.dumps(is_reactive)}"
        >
            <marimo-cell-output>
            {output if output and display_output else ""}
            </marimo-cell-output>
            {code_block}
        </marimo-island>
        """
            ).strip()
        )


class MarimoIslandGenerator:
    """
    Generates Marimo islands for embedding in other pages.

    This is a great way to use another SSG framework that converts
    Python code to HTML using marimo-islands.

    Generally you will want to:

    1. Find all the code snippets and add them to the generator.
    2. Build the app.
    3. Replace all code snippets with the rendered HTML.
    4. Include the header in the <head> tag.

    # Example

    ```python
    from marimo import MarimoIslandGenerator

    generator = MarimoIslandGenerator()
    block1 = generator.add_code("import marimo as mo")
    block2 = generator.add_code("mo.md('Hello, islands!')")

    # Build the app
    app = await generator.build()

    # Render the app
    output = f\"\"\"
    <html>
        <head>
            {generator.render_head()}
        </head>
        <body>
            {block1.render(display_output=False)}
            {block2.render()}
        </body>
    </html>
    \"\"\"
    ```
    """

    def __init__(self, app_id: str = "main"):
        self.has_run = False
        self._app_id = app_id
        self._app = InternalApp(App())
        self._stubs: List[MarimoIslandStub] = []
        self._config = _AppConfig()

    @staticmethod
    def from_file(
        filename: str,
        display_code: bool = False,
    ) -> MarimoIslandGenerator:
        """
        Create a MarimoIslandGenerator and populate MarimoIslandStubs
        using code cells from a marimo *.py file.

        *Args:*

        - filename (str): Marimo .py filename to convert to reactive HTML.
        - display_code (bool): Whether to display the code in HTML snippets.
        """
        path = MarimoPath(filename)
        file_router = AppFileRouter.from_filename(path)
        file_key = file_router.get_unique_file_key()
        assert file_key is not None
        file_manager = file_router.get_file_manager(file_key)

        generator = MarimoIslandGenerator()
        stubs = []
        for cell_data in file_manager.app.cell_manager.cell_data():
            stubs.append(
                generator.add_code(
                    cell_data.code,
                    display_code=display_code,
                )
            )

        generator._stubs = stubs
        generator._config = file_manager.app.config

        return generator

    def add_code(
        self,
        code: str,
        display_code: bool = False,
        display_output: bool = True,
        is_reactive: bool = True,
        is_raw: bool = False,
    ) -> MarimoIslandStub:
        """Add a code cell to the app.

        *Args:*

        - code (str): The code to add to the app.
        - display_code (bool): Whether to display the code in the HTML.
        - display_output (bool): Whether to display the output in the HTML.
        - is_raw (bool): Whether to handled the code without formatting.
        - is_reactive (bool): Whether this code block will run with pyodide.
        """
        if not is_raw:
            code = dedent(code)

        cell_id = self._app.cell_manager.create_cell_id()
        cell_impl = compile_cell(code, cell_id)
        cell_impl.configure(CellConfig(hide_code=False))
        cell = Cell(_name="__", _cell=cell_impl)

        self._app.cell_manager._register_cell(
            cell,
            app=self._app,
        )

        stub = MarimoIslandStub(
            cell_id=cell_id,
            app_id=self._app_id,
            code=code,
            display_code=display_code,
            display_output=display_output,
            is_reactive=is_reactive,
        )
        self._stubs.append(stub)

        return stub

    async def build(self) -> App:
        """
        Build the app. This should be called after adding all the code cells.

        *Returns:*

        - App: The built app.
        """
        if self.has_run:
            raise ValueError("You can only call build() once")

        session = await run_app_until_completion(
            file_manager=AppFileManager.from_app(self._app),
            cli_args={},
        )
        self.has_run = True

        for stub in self._stubs:
            stub._internal_app = self._app
            stub._session_view = session

        return cast(App, self._app)

    def render_head(
        self,
        *,
        version_override: str = __version__,
        _development_url: Union[str, bool] = False,
    ) -> str:
        """
        Render the header for the app.
        This should be included in the <head> tag of the page.

        *Args:*

        - version_override (str): Marimo version to use for loaded js/css.
        - _development_url (str): If True, uses local marimo islands js.
        """

        # This loads:
        # - The marimo islands js
        # - The marimo islands css
        # - Preconnects to Google Fonts (https://stackoverflow.com/questions/73838138)
        # - Fonts from Google Fonts
        #   (otherwise they would get bundled in the css)
        # - Fonts from KaTeX
        #   (otherwise they would get bundled in the css)

        base_url = f"https://cdn.jsdelivr.net/npm/@marimo-team/islands@{version_override}"
        # This should be kept in sync fonts.css in the frontend
        # Since this is embedded on other pages, we want display=swap
        # for the most compatible font loading
        font_url = "https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700&amp;family=Lora&amp;family=PT+Sans:wght@400;700&amp;display=swap"

        fonts = f"""
            <link rel="preconnect" href="https://fonts.googleapis.com" />
            <link
                rel="preconnect"
                href="https://fonts.gstatic.com"
                crossorigin
            />
            <link href="{font_url}" rel="stylesheet" />
            <link
                rel="stylesheet"
                href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"
                integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
                crossorigin="anonymous"
            />
        """.strip()

        if _development_url:
            base_url = "http://localhost:5174"
            if isinstance(_development_url, str):
                base_url = _development_url
            return dedent(
                f"""
                <script
                    type="module"
                    src="{base_url}/src/core/islands/main.ts"
                ></script>
                {fonts}
                """
            ).strip()

        marimo_tags = """
        <marimo-filename hidden></marimo-filename>
        <marimo-mode data-mode='read' hidden></marimo-mode>
        """.strip()

        return dedent(
            f"""
            <script type="module" src="{base_url}/dist/main.js"></script>
            <link
                href="{base_url}/dist/style.css"
                rel="stylesheet"
                crossorigin="anonymous"
            />
            {fonts}
            {marimo_tags}
            """
        ).strip()

    def render_init_island(self) -> str:
        """
        Renders a static html MarimoIsland str which displays a spinning
        initialization loader while Pyodide loads and disappears once
        the kernel is ready to use.
        """

        init_cell_id = self._app.cell_manager.create_cell_id()
        init_input = "<marimo-cell-code hidden> '' </marimo-cell-code>"
        init_output = """
        <div class="marimo" style="--tw-bg-opacity: 0;">
          <div class="flex flex-col items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="size-20 animate-spin text-primary"
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
            </svg>
            <div>Initializing...</div>
          </div>
        </div>
        """
        init_island = dedent(
            f"""
            <marimo-island
                data-app-id="{self._app_id}"
                data-cell-id="{init_cell_id}"
                data-reactive="{json.dumps(True)}"
            >
                <marimo-cell-output>
                {init_output}
                </marimo-cell-output>
                {init_input}
            </marimo-island>
            """
        ).strip()

        return init_island

    def render_body(
        self,
        *,
        include_init_island: bool = True,
        max_width: Optional[str] = None,
        margin: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        Render the body for the app.
        This should be included in the <body> tag of the page.

        *Args:*
        - include_init_island (bool): If True, adds initialization loader.
        - max_width (str): CSS style max_width property.
        - margin (str): CSS style margin property.
        - style (str): CSS style. Overrides max_width and margin.
        """

        rendered_stubs = []
        for stub in self._stubs:
            rendered_stubs.append(stub.render())

        if include_init_island:
            init_island = self.render_init_island()
            rendered_stubs = [init_island] + rendered_stubs

        body = "\n".join(rendered_stubs)

        if margin is None:
            margin = "auto"
        if max_width is None:
            width = self._config.width
            if width == "compact" or width == "normal":
                max_width = "740px"
            elif width == "medium":
                max_width = "1110px"
            else:
                max_width = "none"

        if style is None:
            style = f"margin: {margin}; max-width: {max_width};"

        return dedent(
            f"""
                <div style="{style}">
                  {body}
                </div>
                """
        ).strip()

    def render_html(
        self,
        *,
        version_override: str = __version__,
        _development_url: Union[str, bool] = False,
        include_init_island: bool = True,
        max_width: Optional[str] = None,
        margin: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        Render reactive html for the app.

        *Args:*

        - version_override (str): Marimo version to use for loaded js/css.
        - _development_url (str): If True, uses local marimo islands js.
        - include_init_island (bool): If True, adds initialization loader.
        - max_width (str): CSS style max_width property.
        - margin (str): CSS style margin property.
        - style (str): CSS style. Overrides max_width and margin.
        """
        head = self.render_head(
            version_override=version_override,
            _development_url=_development_url,
        )
        body = self.render_body(
            include_init_island=include_init_island,
            max_width=max_width,
            margin=margin,
            style=style,
        )
        title = (
            self._app_id
            if self._config.app_title is None
            else self._config.app_title
        )

        return dedent(
            f"""<!doctype html>
                <html lang="en">
                    <head>
                      <meta charset="UTF-8" />
                      <title> {title} </title>
                        {head}
                    </head>
                    <body>
                      {body}
                    </body>
                </html>
                """
        ).strip()


def remove_empty_lines(text: str) -> str:
    return "\n".join([line for line in text.split("\n") if line.strip() != ""])
