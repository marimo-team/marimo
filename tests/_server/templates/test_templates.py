from __future__ import annotations

import json
import os
import unittest

from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._server.model import SessionMode
from marimo._server.templates import templates
from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


class TestNotebookPageTemplate(unittest.TestCase):
    def setUp(self):
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.base_url = "/subpath"
        self.user_config = DEFAULT_CONFIG
        self.server_token = "token"
        self.app_config = _AppConfig()
        self.filename = "notebook.py"
        self.mode = SessionMode.RUN

    def test_notebook_page_template(self):
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
        assert self.server_token in result
        assert self.filename in result
        assert "read" in result

    def test_notebook_page_template_no_filename(self):
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
        assert self.server_token in result
        assert "<title>marimo</title>" in result
        assert "read" in result

    def test_notebook_page_template_edit_mode(self):
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
        assert self.server_token in result
        assert self.filename in result
        assert "edit" in result


class TestHomePageTemplate(unittest.TestCase):
    def setUp(self):
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.base_url = "/subpath"
        self.user_config = DEFAULT_CONFIG
        self.server_token = "token"

    def test_home_page_template(self):
        result = templates.home_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.server_token,
        )

        assert self.base_url in result
        assert self.server_token in result
        assert json.dumps(self.user_config) in result
        assert "marimo" in result
        assert json.dumps({}) in result
        assert "" in result
        assert "home" in result


class TestStaticNotebookTemplate(unittest.TestCase):
    def setUp(self):
        root = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "data")
        )
        index_html = os.path.join(root, "index.html")
        with open(index_html, "r") as f:
            self.html = f.read()

        self.user_config = DEFAULT_CONFIG
        self.server_token = "token"
        self.app_config = _AppConfig()
        self.filename = "notebook.py"
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

    def test_static_notebook_template(self):
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filename,
            self.code,
            self.cell_ids,
            self.cell_names,
            self.cell_codes,
            self.cell_configs,
            self.cell_outputs,
            self.cell_console_outputs,
            self.files,
        )

        snapshot("export1.txt", normalize_index_html(result))

    def test_static_notebook_template_no_filename(self):
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            None,
            self.code,
            self.cell_ids,
            self.cell_names,
            self.cell_codes,
            self.cell_configs,
            self.cell_outputs,
            self.cell_console_outputs,
            files=self.files,
        )

        snapshot("export2.txt", normalize_index_html(result))

    def test_static_notebook_template_no_code(self):
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.server_token,
            self.app_config,
            self.filename,
            "",
            [],
            [],
            [],
            [],
            {},
            {},
            {},
        )

        snapshot("export3.txt", normalize_index_html(result))
