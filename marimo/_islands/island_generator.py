# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from textwrap import dedent
from typing import TYPE_CHECKING, List, Optional, Union, cast

from marimo import __version__, _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.cell import Cell, CellConfig
from marimo._ast.compiler import compile_cell
from marimo._messaging.cell_output import CellOutput
from marimo._output.formatting import as_html
from marimo._output.utils import uri_encode_component
from marimo._plugins.stateless.json_output import json_output
from marimo._plugins.ui import code_editor

if TYPE_CHECKING:
    from marimo._server.sessions import Session

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
        self._session: Optional[Session] = None
        self._output: Optional[CellOutput] = None

    @property
    def output(self) -> Optional[CellOutput]:
        # Leave output accessible for direct use for non-interactive cases e.g.
        # pdf.
        if self._output is None:
            assert (
                self._session is not None
            ), "You must call build() before rendering"
            assert (
                self._internal_app is not None
            ), "You must call build() accessing output"
            outputs = self._session.session_view.get_cell_outputs(
                [self._cell_id]
            )
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

        output = handle_mimetypes(self.output) if self.output else None

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
        from marimo._server.export.utils import run_app_until_completion
        from marimo._server.file_manager import AppFileManager

        if self.has_run:
            raise ValueError("You can only call build() once")

        session = await run_app_until_completion(
            file_manager=AppFileManager.from_app(self._app),
            cli_args={},
        )
        self.has_run = True

        for stub in self._stubs:
            stub._internal_app = self._app
            stub._session = session

        return cast(App, self._app)

    def render_head(
        self,
        *,
        version_override: str = __version__,
        _development_url: Union[str | bool] = False,
    ) -> str:
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

        return dedent(
            f"""
            <script type="module" src="{base_url}/dist/main.js"></script>
            <link
                href="{base_url}/dist/style.css"
                rel="stylesheet"
                crossorigin="anonymous"
            />
            {fonts}
            """
        ).strip()


def remove_empty_lines(text: str) -> str:
    return "\n".join([line for line in text.split("\n") if line.strip() != ""])


def handle_mimetypes(output: CellOutput) -> str:
    data = output.data
    if not isinstance(data, str):
        return f"{data}"
    mimetype = output.mimetype
    # Since raw data, without wrapping in an image tag, this is just a huge
    # blob.
    if mimetype.startswith("image/"):
        data = f"<img src='{data}'/>"
    elif mimetype == "application/json":
        data = f"{json_output(json.loads(data))}"
    # TODO: Errors are displayed as just json strings until reactivity kicks
    # in. Ideally, handle application/vnd.marimo+error
    return data
