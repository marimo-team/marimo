# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent
from typing import cast

from marimo import __version__, _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.cell import Cell, CellConfig
from marimo._ast.compiler import compile_cell
from marimo._output.utils import uri_encode_component
from marimo._server.export.utils import run_app_until_completion
from marimo._server.file_manager import AppFileManager

LOGGER = _loggers.marimo_logger()


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
    generator.add_code("import marimo as mo")
    generator.add_code("mo.md('Hello, islands!')")

    # Build the app
    app = await generator.build()

    # Render the app
    output = f\"\"\"
    <html>
        <head>
            {generator.render_header()}
        </head>
        <body>
            {generator.render("import marimo as mo")}
            {generator.render("mo.md('Hello, islands!')")}
        </body>
    </html>
    \"\"\"
    ```
    """

    def __init__(self, app_id: str = "main"):
        self.has_run = False
        self._app_id = app_id
        self._app = InternalApp(App())

    def add_code(
        self,
        code: str,
        *,
        disabled: bool = False,
        hide_code: bool = False,
    ) -> MarimoIslandGenerator:
        """Add a code cell to the app.

        *Args:*

        - code (str): The code to add to the app.
        - disabled (bool, optional): Whether the cell should be disabled.
            Defaults to False.
        - hide_code (bool, optional): Whether the code/output should be hidden.
            Defaults to False.
        """

        cell_id = self._app.cell_manager.create_cell_id()
        cell_impl = compile_cell(code, cell_id)
        cell_impl.configure(CellConfig(disabled=disabled, hide_code=hide_code))
        cell = Cell(_name="__", _cell=cell_impl)

        self._app.cell_manager._register_cell(
            cell,
            app=self._app,
        )

        return self

    async def build(self) -> App:
        """
        Build the app. This should be called after adding all the code cells.

        *Returns:*

        - App: The built app.
        """

        if self.has_run:
            raise ValueError("You can only call build() once")

        self._session = await run_app_until_completion(
            file_manager=AppFileManager.from_app(self._app),
            cli_args={},
        )
        self.has_run = True
        return cast(App, self._app)

    def render_header(self, version_override: str = __version__) -> str:
        """
        Render the header for the app.
        This should be included in the <head> tag of the page.
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

        return dedent(
            f"""
            <script src="{base_url}/dist/main.js"></script>
            <link
                href="{base_url}/dist/styles.css"
                rel="stylesheet"
                crossorigin="anonymous"
            />
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
            """
        ).strip()

    def render(self, code: str) -> str:
        """
        Render the HTML code for the given Python code.
        """

        if not self.has_run:
            raise ValueError("You must call build() before calling render()")

        # Find the cell that has the code
        cell_id = self._app.cell_manager.get_cell_id_by_code(code)
        if cell_id is None:
            LOGGER.warning(f"Could not find cell with code: {code}")
            return ""

        outputs = self._session.session_view.get_cell_outputs([cell_id])
        output = outputs.get(cell_id, None)

        # Cell may not have output
        # (e.g. imports, but still needs to be included)

        return dedent(
            f"""
        <marimo-island data-app-id="{self._app_id}" data-cell-id="{cell_id}">
            <marimo-cell-output>
            {output.data if output else ""}
            </marimo-cell-output>
            <marimo-cell-code hidden>
            {uri_encode_component(code)}
            </marimo-cell-code>
        </marimo-island>
        """
        ).strip()
