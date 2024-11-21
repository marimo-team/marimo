from __future__ import annotations

import json
import os
import unittest

from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._server.export.exporter import hash_code
from marimo._server.model import SessionMode
from marimo._server.templates import templates
from marimo._server.tokens import SkewProtectionToken
from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


class TestNotebookPageTemplate(unittest.TestCase):
    def setUp(self) -> None:
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.base_url = "/subpath"
        self.user_config = DEFAULT_CONFIG
        self.server_token = SkewProtectionToken("token")
        self.app_config = _AppConfig()
        self.filename = "notebook.py"
        self.mode = SessionMode.RUN

    def test_notebook_page_template(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filename,
            self.mode,
        )

        assert self.base_url in result
        assert str(self.server_token) in result
        assert self.filename in result
        assert "read" in result

    def test_notebook_page_template_no_filename(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.server_token,
            self.app_config,
            None,
            self.mode,
        )

        assert self.base_url in result
        assert str(self.server_token) in result
        assert "<title>marimo</title>" in result
        assert "read" in result

    def test_notebook_page_template_edit_mode(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filename,
            SessionMode.EDIT,
        )

        assert self.base_url in result
        assert str(self.server_token) in result
        assert self.filename in result
        assert "edit" in result

    def test_notebook_page_template_custom_css(self) -> None:
        # Create css file
        css = "/* custom css */"

        css_file = os.path.join(os.path.dirname(self.filename), "custom.css")
        with open(css_file, "w") as f:
            f.write(css)

        try:
            result = templates.notebook_page_template(
                self.html,
                self.base_url,
                self.user_config,
                self.server_token,
                _AppConfig(css_file="custom.css"),
                self.filename,
                self.mode,
            )

            assert css in result
        finally:
            os.remove(css_file)

    def test_notebook_page_template_custom_head(self) -> None:
        # Create html head file
        head = """
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-XXXXXXXXXX');
        </script>
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
        """

        head_file = os.path.join(os.path.dirname(self.filename), "head.html")
        with open(head_file, "w") as f:
            f.write(head)

        try:
            result = templates.notebook_page_template(
                self.html,
                self.base_url,
                self.user_config,
                self.server_token,
                _AppConfig(html_head_file="head.html"),
                self.filename,
                self.mode,
            )

            assert head in result
        finally:
            os.remove(head_file)


class TestHomePageTemplate(unittest.TestCase):
    def setUp(self) -> None:
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.base_url = "/subpath"
        self.user_config = DEFAULT_CONFIG
        self.server_token = SkewProtectionToken("token")

    def test_home_page_template(self) -> None:
        result = templates.home_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.server_token,
        )

        assert self.base_url in result
        assert str(self.server_token) in result
        assert json.dumps(self.user_config) in result
        assert "marimo" in result
        assert json.dumps({}) in result
        assert "" in result
        assert "home" in result


class TestStaticNotebookTemplate(unittest.TestCase):
    def setUp(self) -> None:
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.user_config = DEFAULT_CONFIG
        self.server_token = SkewProtectionToken("token")
        self.app_config = _AppConfig()
        self.filename = "notebook.py"
        self.filepath = "path/to/notebook.py"
        self.code = "print('Hello, World!')"
        self.cell_ids = ["cell1", "cell2"]
        self.cell_names = ["Cell 1", "Cell 2"]
        self.cell_codes = ["print('Hello, Cell 1')", "print('Hello, Cell 2')"]
        self.cell_configs = [CellConfig(), CellConfig()]
        self.cell_outputs = {
            "cell1": CellOutput(
                channel=CellChannel.OUTPUT,
                data="Hello, Cell 1",
                mimetype="text/plain",
                timestamp=0,
            )
        }
        self.cell_console_outputs = {
            "cell1": [
                CellOutput(
                    channel=CellChannel.STDOUT,
                    data="Hello, Cell 1",
                    mimetype="text/plain",
                    timestamp=0,
                ),
                CellOutput(
                    channel=CellChannel.STDERR,
                    data="Error in Cell 1",
                    mimetype="text/plain",
                    timestamp=0,
                ),
            ],
            "cell2": [],
        }
        self.files = {"file1": "File 1 content", "file2": "File 2 content"}

    def test_static_notebook_template(self) -> None:
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filepath,
            self.code,
            hash_code(self.code),
            self.cell_ids,
            self.cell_names,
            self.cell_codes,
            self.cell_configs,
            self.cell_outputs,
            self.cell_console_outputs,
            self.files,
        )

        snapshot("export1.txt", normalize_index_html(result))

    def test_static_notebook_template_no_filename(self) -> None:
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            None,
            self.code,
            hash_code(self.code),
            self.cell_ids,
            self.cell_names,
            self.cell_codes,
            self.cell_configs,
            self.cell_outputs,
            self.cell_console_outputs,
            files=self.files,
        )

        snapshot("export2.txt", normalize_index_html(result))

    def test_static_notebook_template_no_code(self) -> None:
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filepath,
            "",
            hash_code(self.code),
            [],
            [],
            [],
            [],
            {},
            {},
            {},
        )

        snapshot("export3.txt", normalize_index_html(result))

    def test_static_notebook_template_with_css(self) -> None:
        # Create css file
        css = "/* custom css */"

        css_file = os.path.join(os.path.dirname(self.filename), "custom.css")
        with open(css_file, "w") as f:
            f.write(css)

        try:
            result = templates.static_notebook_template(
                self.html,
                self.user_config,
                self.server_token,
                _AppConfig(css_file="custom.css"),
                self.filename,
                "",
                hash_code(self.code),
                [],
                [],
                [],
                [],
                {},
                {},
                {},
            )

            snapshot("export4.txt", normalize_index_html(result))
        finally:
            os.remove(css_file)

    def test_static_notebook_template_with_head(self) -> None:
        # Create html head file
        head = """
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-XXXXXXXXXX');
        </script>
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
        """

        head_file = os.path.join(os.path.dirname(self.filename), "head.html")
        with open(head_file, "w") as f:
            f.write(head)

        try:
            result = templates.static_notebook_template(
                self.html,
                self.user_config,
                self.server_token,
                _AppConfig(html_head_file="head.html"),
                self.filename,
                "",
                hash_code(self.code),
                [],
                [],
                [],
                [],
                {},
                {},
                {},
            )

            snapshot("export5.txt", normalize_index_html(result))
        finally:
            os.remove(head_file)
