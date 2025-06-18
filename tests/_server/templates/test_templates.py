from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Literal

from marimo._utils.code import hash_code

from marimo._ast.app_config import _AppConfig
from marimo._config.config import (
    MarimoConfig,
    PartialMarimoConfig,
    merge_default_config,
)
from marimo._schemas.notebook import (
    NotebookCell,
    NotebookCellConfig,
    NotebookMetadata,
    NotebookV1,
)
from marimo._schemas.session import (
    VERSION,
    Cell,
    DataOutput,
    NotebookSessionMetadata,
    NotebookSessionV1,
    StreamOutput,
)
from marimo._server.model import SessionMode
from marimo._server.templates import templates
from marimo._server.tokens import SkewProtectionToken
from tests._server.templates.utils import normalize_index_html
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)
default_config = merge_default_config({})


def _assert_no_leftover_replacements(result: str) -> None:
    has_replacement = "{{" in result and "}}" in result
    assert not has_replacement, f"Found {{}} in {result}"


class TestNotebookPageTemplate(unittest.TestCase):
    def setUp(self) -> None:
        tmp_path = Path(tempfile.mkdtemp())
        self.tmp_path = tmp_path
        root = Path(__file__).parent / "data"
        index_html = root / "index.html"
        self.html = index_html.read_text(encoding="utf-8")

        self.base_url = "/subpath"
        self.user_config: MarimoConfig = default_config
        self.config_overrides: PartialMarimoConfig = {}
        self.server_token = SkewProtectionToken("token")
        self.app_config = _AppConfig()
        self.filename = tmp_path / "notebook.py"
        self.mode = SessionMode.RUN

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path)

    def test_notebook_page_template(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            self.mode,
        )

        assert self.base_url not in result
        assert str(self.server_token) in result
        assert self.filename.name in result
        assert "read" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_no_filename(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            None,
            self.mode,
        )

        assert self.base_url not in result
        assert str(self.server_token) in result
        assert "<title>marimo</title>" in result
        assert "read" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_edit_mode(self) -> None:
        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            SessionMode.EDIT,
        )

        assert self.base_url not in result
        assert str(self.server_token) in result
        assert self.filename.name in result
        assert "edit" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_custom_css(self) -> None:
        # Create css file
        css = "/* custom css */"

        css_file = self.filename.parent / "custom.css"
        css_file.write_text(css)

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
            _AppConfig(css_file="custom.css"),
            str(self.filename),
            self.mode,
        )

        assert css in result
        _assert_no_leftover_replacements(result)

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

        head_file = self.filename.parent / "head.html"
        head_file.write_text(head)

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
            _AppConfig(html_head_file="head.html"),
            str(self.filename),
            self.mode,
        )

        assert head in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_with_custom_css_config(self) -> None:
        # Create CSS files
        css1 = "/* custom css 1 */"
        css2 = "/* custom css 2 */"

        css_file1 = self.filename.parent / "custom1.css"
        css_file2 = self.filename.parent / "custom2.css"
        css_file1.write_text(css1)
        css_file2.write_text(css2)

        # Update config with custom CSS paths
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = ["custom1.css", "custom2.css"]

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            self.mode,
        )

        assert css1 in result
        assert css2 in result
        assert "<style title='marimo-custom'>" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_with_absolute_custom_css(self) -> None:
        # Create CSS file with absolute path
        css = "/* absolute path css */"
        css_file = self.filename.parent / "absolute.css"
        css_file.write_text(css)

        # Update config with absolute CSS path
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = [str(css_file)]

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            self.mode,
        )

        assert css in result
        assert "<style title='marimo-custom'>" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_with_config_overrides_custom_css(
        self,
    ) -> None:
        # Create CSS files
        css1 = "/* config override css */"
        css_file1 = self.filename.parent / "override.css"
        css_file1.write_text(css1)

        # Update config_overrides with custom CSS path
        config_overrides = self.config_overrides.copy()
        config_overrides["display"] = {"custom_css": ["override.css"]}

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            self.user_config,
            config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            self.mode,
        )

        assert css1 in result
        assert "<style title='marimo-custom'>" in result
        _assert_no_leftover_replacements(result)

    def test_notebook_page_template_with_nonexistent_custom_css(self) -> None:
        # Update config with nonexistent CSS path
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = ["nonexistent.css"]

        result = templates.notebook_page_template(
            self.html,
            self.base_url,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            self.mode,
        )

        assert "nonexistent.css" in result
        assert "<style title='marimo-custom'>" not in result
        _assert_no_leftover_replacements(result)


class TestHomePageTemplate(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(tempfile.mkdtemp())
        root = Path(__file__).parent / "data"
        index_html = root / "index.html"
        self.html = index_html.read_text(encoding="utf-8")

        self.base_url = "/subpath"
        self.user_config: MarimoConfig = default_config
        self.config_overrides: PartialMarimoConfig = {
            "formatting": {"line_length": 100},
        }
        self.server_token = SkewProtectionToken("token")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path)

    def test_home_page_template(self) -> None:
        result = templates.home_page_template(
            self.html,
            self.base_url,
            self.user_config,
            self.config_overrides,
            self.server_token,
        )

        assert self.base_url not in result
        assert str(self.server_token) in result
        assert json.dumps(self.user_config, sort_keys=True) in result
        assert "marimo" in result
        assert json.dumps({}) in result
        assert "" in result
        assert "home" in result
        _assert_no_leftover_replacements(result)


class TestStaticNotebookTemplate(unittest.TestCase):
    def setUp(self) -> None:
        tmp_path = Path(tempfile.mkdtemp())
        self.tmp_path = tmp_path
        root = Path(__file__).parent / "data"
        index_html = root / "index.html"
        self.html = index_html.read_text(encoding="utf-8")

        self.user_config = default_config
        self.config_overrides: PartialMarimoConfig = {
            "formatting": {"line_length": 100},
        }
        self.server_token = SkewProtectionToken("token")
        self.app_config = _AppConfig()
        self.filename = tmp_path / "notebook.py"
        self.filepath = "path/to/notebook.py"
        self.code = "print('Hello, World!')"

        # Create session and notebook snapshots
        self.session_snapshot = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[
                Cell(
                    id="cell1",
                    code_hash="abc123",
                    outputs=[
                        DataOutput(
                            type="data",
                            data={
                                "text/plain": "Hello, Cell 1",
                            },
                        )
                    ],
                    console=[
                        StreamOutput(
                            type="stream",
                            name="stdout",
                            text="Hello, Cell 1",
                        ),
                        StreamOutput(
                            type="stream",
                            name="stderr",
                            text="Error in Cell 1",
                        ),
                    ],
                ),
                Cell(
                    id="cell2",
                    code_hash="def456",
                    outputs=[],
                    console=[],
                ),
            ],
        )

        self.notebook_snapshot = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[
                NotebookCell(
                    id="cell1",
                    code="print('Hello, Cell 1')",
                    code_hash=hash_code("print('Hello, Cell 1')"),
                    name="Cell 1",
                    config=NotebookCellConfig(),
                ),
                NotebookCell(
                    id="cell2",
                    code="print('Hello, Cell 2')",
                    code_hash=hash_code("print('Hello, Cell 2')"),
                    name="Cell 2",
                    config=NotebookCellConfig(),
                ),
            ],
        )

        self.files = {"file1": "File 1 content", "file2": "File 2 content"}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path)

    def test_static_notebook_template(self) -> None:
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            self.filepath,
            self.code,
            hash_code(self.code),
            self.session_snapshot,
            self.notebook_snapshot,
            self.files,
        )

        snapshot("export1.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_no_filename(self) -> None:
        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            None,
            self.code,
            hash_code(self.code),
            self.session_snapshot,
            self.notebook_snapshot,
            files=self.files,
        )

        snapshot("export2.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_no_code(self) -> None:
        # Create empty snapshots for no-code case
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            self.filepath,
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        snapshot("export3.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_with_css(self) -> None:
        # Create css file
        css = "/* custom css */"

        css_file = self.filename.parent / "custom.css"
        css_file.write_text(css)

        # Create empty snapshots
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.config_overrides,
            self.server_token,
            _AppConfig(css_file="custom.css"),
            str(self.filename),
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        snapshot("export4.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

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

        head_file = self.filename.parent / "head.html"
        head_file.write_text(head)

        # Create empty snapshots
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            self.user_config,
            self.config_overrides,
            self.server_token,
            _AppConfig(html_head_file="head.html", app_title="My App"),
            str(self.filename),
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        snapshot("export5.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_with_custom_css_config(self) -> None:
        # Create CSS files
        css1 = "/* custom css 1 */"
        css2 = "/* custom css 2 */"

        css_file1 = self.filename.parent / "custom1.css"
        css_file2 = self.filename.parent / "custom2.css"
        css_file1.write_text(css1)
        css_file2.write_text(css2)

        # Update config with custom CSS paths
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = ["custom1.css", "custom2.css"]

        # Create empty snapshots
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        assert css1 in result
        assert css2 in result
        assert "<style title='marimo-custom'>" in result
        snapshot("export6.txt", normalize_index_html(result))
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_with_absolute_custom_css(self) -> None:
        # Create CSS file with absolute path
        css = "/* absolute path css */"
        css_file = self.filename.parent / "absolute.css"
        css_file.write_text(css)

        # Update config with absolute CSS path
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = [str(css_file)]

        # Create empty snapshots
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        assert css in result
        assert "<style title='marimo-custom'>" in result
        _assert_no_leftover_replacements(result)

    def test_static_notebook_template_with_nonexistent_custom_css(
        self,
    ) -> None:
        # Update config with nonexistent CSS path
        config = merge_default_config(self.user_config)
        config["display"]["custom_css"] = ["nonexistent.css"]

        # Create empty snapshots
        empty_session = NotebookSessionV1(
            version=VERSION,
            metadata=NotebookSessionMetadata(marimo_version="0.1.0"),
            cells=[],
        )
        empty_notebook = NotebookV1(
            version=VERSION,
            metadata=NotebookMetadata(marimo_version="0.1.0"),
            cells=[],
        )

        result = templates.static_notebook_template(
            self.html,
            config,
            self.config_overrides,
            self.server_token,
            self.app_config,
            str(self.filename),
            "",
            hash_code(self.code),
            empty_session,
            empty_notebook,
            {},
        )

        assert "nonexistent.css" in result
        assert "<style title='marimo-custom'>" not in result
        _assert_no_leftover_replacements(result)


class TestWasmNotebookTemplate(unittest.TestCase):
    def setUp(self) -> None:
        tmp_path = Path(tempfile.mkdtemp())
        self.tmp_path = tmp_path
        root = Path(__file__).parent / "data"
        index_html = root / "index.html"
        self.html = index_html.read_text(encoding="utf-8")

        self.version = "1.0.0"
        self.filename = tmp_path / "notebook.py"
        self.mode: Literal["edit", "run"] = "run"
        self.user_config: MarimoConfig = default_config
        self.app_config = _AppConfig()
        self.code = "print('Hello, World!')"
        self.config_overrides: PartialMarimoConfig = {}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path)

    def test_wasm_notebook_template(self) -> None:
        result = templates.wasm_notebook_template(
            html=self.html,
            version=self.version,
            filename=str(self.filename),
            mode=self.mode,
            user_config=self.user_config,
            config_overrides=self.config_overrides,
            app_config=self.app_config,
            code=self.code,
            show_code=False,
        )

        assert self.filename.name in result
        assert self.mode in result
        assert json.dumps(self.user_config, sort_keys=True) in result
        assert '<marimo-wasm hidden="">' in result
        assert '<marimo-code hidden="">' in result
        assert '"showAppCode": false' in result
        assert "<title>notebook</title>" in result
        _assert_no_leftover_replacements(result)

    def test_wasm_notebook_template_custom_css_and_assets(self) -> None:
        # Create css file
        css = "/* custom css */"

        css_file = self.filename.parent / "custom.css"
        css_file.write_text(css)

        result = templates.wasm_notebook_template(
            html=self.html,
            version=self.version,
            filename=str(self.filename),
            mode=self.mode,
            user_config=self.user_config,
            config_overrides=self.config_overrides,
            app_config=_AppConfig(css_file="custom.css"),
            code=self.code,
            asset_url="https://my.cdn.com",
            show_code=True,
        )

        assert css in result
        assert '<marimo-wasm hidden="">' in result
        assert "https://my.cdn.com/assets/" in result
        assert '<marimo-code hidden="">' in result
        assert '"showAppCode": true' in result
        _assert_no_leftover_replacements(result)

    def test_wasm_notebook_template_custom_head(self) -> None:
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

        head_file = self.filename.parent / "head.html"
        head_file.write_text(head)

        result = templates.wasm_notebook_template(
            html=self.html,
            version=self.version,
            filename=str(self.filename),
            mode=self.mode,
            user_config=self.user_config,
            config_overrides=self.config_overrides,
            app_config=_AppConfig(
                html_head_file="head.html", app_title="My App"
            ),
            code=self.code,
            show_code=False,
        )

        assert head in result
        assert '<marimo-wasm hidden="">' in result
        assert '<marimo-code hidden="">' in result
        assert '"showAppCode": false' in result
        assert "#save-button" in result
        assert "#filename-input" in result
        assert "<title>My App</title>" in result
        _assert_no_leftover_replacements(result)
