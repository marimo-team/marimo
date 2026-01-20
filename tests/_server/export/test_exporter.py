from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.load import load_app
from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._messaging.notification import CellNotification
from marimo._server.export import (
    export_as_wasm,
    run_app_until_completion,
)
from marimo._server.export.exporter import Exporter
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._session.notebook import AppFileManager
from marimo._session.state.session_view import SessionView
from marimo._utils.marimo_path import MarimoPath
from tests.mocks import delete_lines_with_files, snapshotter

if TYPE_CHECKING:
    from pathlib import Path

SELF_DIR = pathlib.Path(__file__).parent
FIXTURES_DIR = SELF_DIR / "fixtures" / "apps"
snapshot = snapshotter(__file__)

HAS_NBFORMAT = DependencyManager.nbformat.has()
HAS_DEPS = (
    HAS_NBFORMAT
    and DependencyManager.polars.has()
    and DependencyManager.altair.has()
    and DependencyManager.matplotlib.has()
)


def _print_messages(messages: list[CellNotification]) -> str:
    result: list[dict[str, Any]] = []
    for message in messages:
        result.append(
            {
                "output": (
                    message.output.data if message.output is not None else None
                ),
                "console": (
                    [
                        output.data if output else None
                        for output in _as_list(message.console)
                    ]
                    if message.console is not None
                    else None
                ),
                "status": message.status,
            }
        )
    # Use msgspec for encoding, then format with json for readable snapshots
    encoded = encode_json_str(result)
    return json.dumps(json.loads(encoded), indent=2)


def _as_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data  # type: ignore
    return [data]


def _load_fixture_app(name: str) -> InternalApp:
    """Load a fixture app by name."""
    app = load_app(FIXTURES_DIR / f"{name}.py")
    assert app is not None
    return InternalApp(app)


# run_until_completion


async def test_run_until_completion_with_stop() -> None:
    """Test run until completion with mo.stop()."""
    internal_app = _load_fixture_app("with_stop")
    file_manager = AppFileManager.from_app(internal_app)

    session_view, did_error = await run_app_until_completion(
        file_manager,
        cli_args={},
        argv=None,
    )
    assert did_error is False
    cell_notifications = [
        op
        for op in session_view.notifications
        if isinstance(op, CellNotification)
    ]
    snapshot(
        "run_until_completion_with_stop.txt",
        _print_messages(cell_notifications),
    )


@pytest.mark.skipif(
    sys.version_info >= (3, 13), reason="3.13 has different stack trace format"
)
@pytest.mark.xfail(reason="flakey", strict=False)
async def test_run_until_completion_with_stack_trace() -> None:
    """Test run until completion with stack trace from exception."""

    app = App()

    @app.cell()
    def _():
        print("running internal tests")
        return

    @app.cell()
    def _():
        import sys

        sys.stderr.write("internal error\n")
        return

    @app.cell()
    def _():
        given_password = "test"
        if given_password != "s3cret":
            raise ValueError(
                "Failed to authenticate. The correct password is 's3cret'."
            )
        return

    file_manager = AppFileManager.from_app(InternalApp(app))

    session_view, did_error = await run_app_until_completion(
        file_manager, cli_args={}, argv=None
    )
    assert did_error is True
    cell_notifications = [
        op
        for op in session_view.notifications
        if isinstance(op, CellNotification)
    ]

    messages = _print_messages(cell_notifications)
    snapshot(
        "run_until_completion_with_stack_trace.txt",
        delete_lines_with_files(messages),
    )


@pytest.mark.flaky(reruns=3)
@patch("marimo._server.export.echo")
async def test_run_until_completion_with_console_output(
    mock_echo: MagicMock,
) -> None:
    """Test run until completion with console output."""
    internal_app = _load_fixture_app("with_console_output")
    file_manager = AppFileManager.from_app(internal_app)

    session_view, did_error = await run_app_until_completion(
        file_manager,
        cli_args={},
        argv=None,
    )
    assert did_error is False

    def _assert_contents() -> None:
        mock_echo.assert_any_call("hello stdout", file=ANY, nl=False)
        mock_echo.assert_any_call("hello stderr", file=ANY, nl=False)

    # Console output notifications arrive asynchronously after CompletedRun.
    n_tries = 0
    limit = 50
    while n_tries <= limit:
        try:
            _assert_contents()
            break
        except Exception:
            n_tries += 1
            await asyncio.sleep(0.1)
    if n_tries > limit:
        _assert_contents()

    cell_notifications = [
        op
        for op in session_view.notifications
        if isinstance(op, CellNotification)
    ]
    snapshot(
        "run_until_completion_with_console_output.txt",
        _print_messages(cell_notifications),
    )


# WASM export


@pytest.mark.parametrize(
    ("mode", "expected_mode_in_content"),
    [
        ("edit", '"mode": "edit"'),
        ("run", '"mode": "read"'),
    ],
)
async def test_export_wasm(mode: str, expected_mode_in_content: str) -> None:
    """Test WASM export in edit and run modes."""
    internal_app = _load_fixture_app("basic")
    file_manager = AppFileManager.from_app(internal_app)
    exporter = Exporter()

    content, filename = exporter.export_as_wasm(
        filename=file_manager.filename,
        app=file_manager.app,
        display_config=DEFAULT_CONFIG["display"],
        mode=mode,
        code=file_manager.app.to_py(),
        show_code=True,
    )

    assert filename == "notebook.wasm.html"
    assert "alert(" in content
    assert expected_mode_in_content in content


async def test_export_html_with_layout(tmp_path: Path) -> None:
    """Test HTML export with layout file."""
    test_file = tmp_path / "test.py"
    test_file.write_text((FIXTURES_DIR / "with_layout.py").read_text())

    # Create the layout file
    layout_file = tmp_path / "layouts" / "layout.json"
    layout_file.parent.mkdir(parents=True, exist_ok=True)
    layout_file.write_text('{"type": "slides", "data": {}}')

    result = export_as_wasm(
        path=MarimoPath(test_file),
        mode="edit",
        show_code=True,
    )
    assert result.did_error is False
    assert "layout.json" not in result.contents
    assert "data:application/json" in result.contents


# HTML export


@pytest.mark.parametrize(
    ("include_code", "check_code_present", "check_code_absent"),
    [
        (True, ["return secret_value"], []),
        (False, [], ["secret_value", "should_not_appear"]),
    ],
    ids=["with_code", "without_code"],
)
def test_export_as_html_code_inclusion(
    session_view: SessionView,
    include_code: bool,
    check_code_present: list[str],
    check_code_absent: list[str],
) -> None:
    """Test HTML export with and without code inclusion."""

    app = App()

    @app.cell()
    def test_cell():
        secret_value = "should_not_appear"
        print("visible output")
        return secret_value

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="visible output",
        ),
        console=[
            CellOutput(
                channel=CellChannel.STDOUT,
                mimetype="text/plain",
                data="console message",
            )
        ],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = (
        "secret_value = 'should_not_appear'\n"
        "print('visible output')\n"
        "return secret_value"
    )

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=not include_code,
        files=[],
        include_code=include_code,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    # Output should always be visible
    assert "visible output" in html

    for text in check_code_present:
        assert text in html
    for text in check_code_absent:
        assert text not in html


def test_export_as_html_with_serialization(session_view: SessionView) -> None:
    """Test HTML export uses new serialization approach correctly."""

    app = App()

    @app.cell()
    def cell_1():
        print("Hello World")
        return 10

    @app.cell()
    def cell_2():
        import marimo as mo

        mo.md("# Markdown Cell")
        return (mo,)

    file_manager = AppFileManager.from_app(InternalApp(app))

    # Add some test data to session view
    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="10",
        ),
        console=[
            CellOutput(
                channel=CellChannel.STDOUT,
                mimetype="text/plain",
                data="Hello World",
            )
        ],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = (
        "print('Hello World')\nreturn 10"
    )

    session_view.cell_notifications[cell_ids[1]] = CellNotification(
        cell_id=cell_ids[1],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data="<h1>Markdown Cell</h1>",
        ),
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[1]] = (
        "import marimo as mo\nmo.md('# Markdown Cell')\nreturn (mo,)"
    )

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=True,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    assert "Hello World" in html
    assert "Markdown Cell" in html
    assert 'data-marimo="true"' in html


def test_export_as_html_with_files(session_view: SessionView) -> None:
    """Test HTML export includes virtual files."""

    app = App()

    @app.cell()
    def test_cell():
        return "test"

    file_manager = AppFileManager.from_app(InternalApp(app))

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=None,
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = "return 'test'"

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=["/@file/10-test.txt"],
        include_code=True,
    )

    with patch(
        "marimo._server.export.exporter.read_virtual_file"
    ) as mock_read:
        mock_read.return_value = b"test file content"

        html, filename = exporter.export_as_html(
            filename=file_manager.filename,
            app=file_manager.app,
            session_view=session_view,
            display_config=DEFAULT_CONFIG["display"],
            request=request,
        )

    assert filename == "notebook.html"
    assert "data:" in html


def test_export_as_html_with_cell_configs(session_view: SessionView) -> None:
    """Test HTML export preserves cell configurations through serialization."""

    app = App()

    @app.cell(hide_code=True, disabled=True, column=1)
    def configured_cell():
        return "configured"

    file_manager = AppFileManager.from_app(InternalApp(app))

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="configured",
        ),
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = "return 'configured'"

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=True,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    assert "hide_code" in html or "hideCode" in html
    assert "configured" in html


def test_export_as_html_preserves_output_order(
    session_view: SessionView,
) -> None:
    """Test HTML export preserves cell execution order in session snapshot."""

    app = App()

    @app.cell()
    def cell_first():
        return "first"

    @app.cell()
    def cell_second():
        return "second"

    @app.cell()
    def cell_third():
        return "third"

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    for i, cell_id in enumerate(cell_ids):
        session_view.cell_notifications[cell_id] = CellNotification(
            cell_id=cell_id,
            status="idle",
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data=f"output_{i}",
            ),
            console=[],
            timestamp=i,
        )
        session_view.last_executed_code[cell_id] = f"return 'output_{i}'"

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=True,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    assert "output_0" in html
    assert "output_1" in html
    assert "output_2" in html


def test_export_as_html_with_error_outputs(session_view: SessionView) -> None:
    """Test HTML export handles error outputs correctly."""
    from marimo._messaging.errors import MarimoExceptionRaisedError

    app = App()

    @app.cell()
    def error_cell():
        raise ValueError("Test error")

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    error = MarimoExceptionRaisedError(
        exception_type="ValueError",
        msg="Test error",
        raising_cell=cell_ids[0],
    )

    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput.errors([error]),
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = (
        "raise ValueError('Test error')"
    )

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=True,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    assert "Test error" in html or "ValueError" in html


def test_export_as_html_code_hash_consistency(
    session_view: SessionView,
) -> None:
    """Test HTML export includes correct code hash regardless of include_code."""
    import re

    app = App()

    @app.cell()
    def test_cell():
        return "test"

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=None,
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = "return 'test'"

    exporter = Exporter()

    # Test with include_code=True
    request_with_code = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=True,
    )

    html_with_code, _ = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request_with_code,
    )

    # Test with include_code=False
    request_without_code = ExportAsHTMLRequest(
        download=True,
        files=[],
        include_code=False,
    )

    html_without_code, _ = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request_without_code,
    )

    # Extract code hash from both HTML outputs
    hash_pattern = r"<marimo-code-hash[^>]*>([a-f0-9]+)</marimo-code-hash>"

    hash_with_code = re.search(hash_pattern, html_with_code)
    hash_without_code = re.search(hash_pattern, html_without_code)

    assert hash_with_code is not None, "Code hash not found in HTML with code"
    assert hash_without_code is not None, (
        "Code hash not found in HTML without code"
    )
    assert hash_with_code.group(1) == hash_without_code.group(1), (
        "Code hashes should be identical"
    )

    assert '"code": ""' in html_without_code, (
        "Cell code should be empty when include_code=False"
    )
    assert '"code": "return' in html_with_code, (
        "Cell code should be present when include_code=True"
    )


# HTML export virtual file replacement tests


def test_export_html_replaces_virtual_files_in_outputs(
    session_view: SessionView,
) -> None:
    """Test that virtual file URLs in HTML outputs are replaced with data URIs."""

    app = App()

    @app.cell()
    def test_cell():
        import marimo as mo

        return mo.image(src="test.png")

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    html_with_virtual_file = (
        '<img src="./@file/100-test.png" alt="Test image">'
    )

    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data=html_with_virtual_file,
        ),
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = (
        "import marimo as mo\nreturn mo.image(src='test.png')"
    )

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=["/@file/100-test.png"],
        include_code=True,
    )

    with patch(
        "marimo._convert.common.dom_traversal.read_virtual_file"
    ) as mock_read:
        mock_read.return_value = b"fake_image_data"

        html, filename = exporter.export_as_html(
            filename=file_manager.filename,
            app=file_manager.app,
            session_view=session_view,
            display_config=DEFAULT_CONFIG["display"],
            request=request,
        )

    assert filename == "notebook.html"
    assert "./@file/100-test.png" not in html
    assert "data:image/png;base64," in html

    expected_b64 = base64.b64encode(b"fake_image_data").decode()
    assert expected_b64 in html


def test_export_html_replaces_multiple_virtual_files_complex(
    session_view: SessionView,
) -> None:
    """Test virtual file replacement with multiple files and nested structures."""

    app = App()

    @app.cell()
    def cell_1():
        import marimo as mo

        return mo.image(src="chart.png")

    @app.cell()
    def cell_2():
        import marimo as mo

        return mo.md("![Plot](./@file/200-plot.png)")

    @app.cell()
    def cell_3():
        return '<div><img src="./@file/300-diagram.svg"><img src="https://example.com/external.png"></div>'

    file_manager = AppFileManager.from_app(InternalApp(app))
    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    # Cell 1: Image with virtual file
    session_view.cell_notifications[cell_ids[0]] = CellNotification(
        cell_id=cell_ids[0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data='<img src="./@file/100-chart.png" alt="Chart">',
        ),
        console=[],
        timestamp=0,
    )
    session_view.last_executed_code[cell_ids[0]] = (
        "import marimo as mo\nreturn mo.image(src='chart.png')"
    )

    # Cell 2: Markdown with virtual file
    session_view.cell_notifications[cell_ids[1]] = CellNotification(
        cell_id=cell_ids[1],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data='<p><img src="./@file/200-plot.png" alt="Plot"></p>',
        ),
        console=[],
        timestamp=1,
    )
    session_view.last_executed_code[cell_ids[1]] = (
        "import marimo as mo\nreturn mo.md('![Plot](./@file/200-plot.png)')"
    )

    # Cell 3: Mixed - virtual file and external URL
    session_view.cell_notifications[cell_ids[2]] = CellNotification(
        cell_id=cell_ids[2],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data='<div><img src="./@file/300-diagram.svg"><img src="https://example.com/external.png"></div>',
        ),
        console=[],
        timestamp=2,
    )
    session_view.last_executed_code[cell_ids[2]] = (
        'return \'<div><img src="./@file/300-diagram.svg">'
        '<img src="https://example.com/external.png"></div>\''
    )

    exporter = Exporter()
    request = ExportAsHTMLRequest(
        download=True,
        files=[
            "/@file/100-chart.png",
            "/@file/200-plot.png",
            "/@file/300-diagram.svg",
            "/@file/400-unused.txt",
        ],
        include_code=True,
    )

    def mock_read_side_effect(filename: str, byte_length: int) -> bytes:
        del byte_length
        if filename == "chart.png":
            return b"chart_data"
        elif filename == "plot.png":
            return b"plot_data"
        elif filename == "diagram.svg":
            return b"<svg>diagram</svg>"
        elif filename == "unused.txt":
            return b"unused_content"
        return b"default_data"

    with (
        patch(
            "marimo._convert.common.dom_traversal.read_virtual_file"
        ) as mock_read_dom,
        patch(
            "marimo._server.export.exporter.read_virtual_file"
        ) as mock_read_exporter,
    ):
        mock_read_dom.side_effect = mock_read_side_effect
        mock_read_exporter.side_effect = mock_read_side_effect

        html, filename = exporter.export_as_html(
            filename=file_manager.filename,
            app=file_manager.app,
            session_view=session_view,
            display_config=DEFAULT_CONFIG["display"],
            request=request,
        )

    assert filename == "notebook.html"

    chart_b64 = base64.b64encode(b"chart_data").decode()
    plot_b64 = base64.b64encode(b"plot_data").decode()
    diagram_b64 = base64.b64encode(b"<svg>diagram</svg>").decode()

    assert chart_b64 in html, "Chart data should be embedded as base64"
    assert plot_b64 in html, "Plot data should be embedded as base64"
    assert diagram_b64 in html, "Diagram data should be embedded as base64"

    assert "data:image/png;base64," in html
    assert "data:image/svg+xml;base64," in html
    assert "https://example.com/external.png" in html


class TestPDFExport:
    def test_export_as_pdf_requires_dependencies(
        self,
        session_view: SessionView,
    ) -> None:
        """Test that PDF export raises error when dependencies are missing."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Mock nbformat as missing
        with patch.object(Dependency, "has", return_value=False):
            with pytest.raises(ManyModulesNotFoundError) as excinfo:
                exporter.export_as_pdf(
                    app=file_manager.app,
                    session_view=session_view,
                    webpdf=False,
                )

            assert "for PDF export" in str(excinfo.value)

    def test_export_as_pdf_webpdf_requires_playwright(
        self,
        session_view: SessionView,
    ) -> None:
        """Test that webpdf mode requires playwright dependency."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Simulate nbformat and nbconvert available, but playwright missing
        def mock_has(self: Dependency, quiet: bool = False) -> bool:
            del quiet
            if self.pkg == "playwright":
                return False
            if self.pkg in ("nbformat", "nbconvert"):
                return True
            return False

        with patch.object(Dependency, "has", mock_has):
            with pytest.raises(ManyModulesNotFoundError) as excinfo:
                exporter.export_as_pdf(
                    app=file_manager.app,
                    session_view=session_view,
                    webpdf=True,
                )

            assert "playwright" in excinfo.value.package_names

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has()
        or not DependencyManager.nbconvert.has(),
        reason="nbformat or nbconvert not installed",
    )
    def test_export_as_pdf_non_webpdf_mode(
        self,
        session_view: SessionView,
    ) -> None:
        """Test PDF export in non-webpdf mode (mocked)."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Mock PDFExporter to avoid requiring LaTeX
        mock_exporter_instance = MagicMock()
        mock_exporter_instance.from_notebook_node.return_value = (
            b"mock_pdf_data",
            {},
        )

        with patch("nbconvert.PDFExporter") as mock_pdf_exporter:
            mock_pdf_exporter.return_value = mock_exporter_instance

            result = exporter.export_as_pdf(
                app=file_manager.app,
                session_view=session_view,
                webpdf=False,
            )

            assert result == b"mock_pdf_data"
            mock_pdf_exporter.assert_called_once()
            mock_exporter_instance.from_notebook_node.assert_called_once()

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has()
        or not DependencyManager.nbconvert.has(),
        reason="nbformat or nbconvert not installed",
    )
    def test_export_as_pdf_webpdf_mode(
        self,
        session_view: SessionView,
    ) -> None:
        """Test PDF export in webpdf mode (mocked)."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Mock WebPDFExporter
        mock_exporter_instance = MagicMock()
        mock_exporter_instance.from_notebook_node.return_value = (
            b"mock_webpdf_data",
            {},
        )

        # Mock playwright as available
        with (
            patch.object(
                DependencyManager.playwright, "has", return_value=True
            ),
            patch("nbconvert.WebPDFExporter") as mock_webpdf_exporter,
        ):
            mock_webpdf_exporter.return_value = mock_exporter_instance

            result = exporter.export_as_pdf(
                app=file_manager.app,
                session_view=session_view,
                webpdf=True,
            )

            assert result == b"mock_webpdf_data"
            mock_webpdf_exporter.assert_called_once()
            # Verify allow_chromium_download is set
            assert mock_exporter_instance.allow_chromium_download is True

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has()
        or not DependencyManager.nbconvert.has(),
        reason="nbformat or nbconvert not installed",
    )
    def test_export_as_pdf_returns_none_on_invalid_data(
        self,
        session_view: SessionView,
    ) -> None:
        """Test PDF export returns None when exporter returns non-bytes data."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Mock PDFExporter to return invalid data
        mock_exporter_instance = MagicMock()
        mock_exporter_instance.from_notebook_node.return_value = (
            "not_bytes",  # Invalid - should be bytes
            {},
        )

        with patch("nbconvert.PDFExporter") as mock_pdf_exporter:
            mock_pdf_exporter.return_value = mock_exporter_instance

            result = exporter.export_as_pdf(
                app=file_manager.app, session_view=session_view, webpdf=False
            )

            assert result is None

    @pytest.mark.skipif(
        not DependencyManager.nbformat.has()
        or not DependencyManager.nbconvert.has(),
        reason="nbformat or nbconvert not installed",
    )
    def test_export_as_pdf_falls_back_to_webpdf_on_oserror(
        self,
        session_view: SessionView,
    ) -> None:
        """Test PDF export falls back to webpdf when standard PDF fails with OSError."""

        app = App()

        @app.cell()
        def test_cell():
            return "test"

        file_manager = AppFileManager.from_app(InternalApp(app))
        exporter = Exporter()

        # Mock PDFExporter to raise OSError (pandoc/xelatex not found)
        mock_pdf_exporter_instance = MagicMock()
        mock_pdf_exporter_instance.from_notebook_node.side_effect = OSError(
            "xelatex not found"
        )

        # Mock WebPDFExporter to succeed
        mock_webpdf_exporter_instance = MagicMock()
        mock_webpdf_exporter_instance.from_notebook_node.return_value = (
            b"fallback_webpdf_data",
            {},
        )

        with (
            patch("nbconvert.PDFExporter") as mock_pdf_exporter,
            patch("nbconvert.WebPDFExporter") as mock_webpdf_exporter,
        ):
            mock_pdf_exporter.return_value = mock_pdf_exporter_instance
            mock_webpdf_exporter.return_value = mock_webpdf_exporter_instance

            result = exporter.export_as_pdf(
                app=file_manager.app,
                session_view=session_view,
                webpdf=False,  # Request standard PDF, but it should fall back
            )

            # Should fall back to webpdf and succeed
            assert result == b"fallback_webpdf_data"
            # PDFExporter was tried first
            mock_pdf_exporter.assert_called_once()
            mock_pdf_exporter_instance.from_notebook_node.assert_called_once()
            # WebPDFExporter was used as fallback
            mock_webpdf_exporter.assert_called_once()
            mock_webpdf_exporter_instance.from_notebook_node.assert_called_once()
            # Verify allow_chromium_download is set on fallback
            assert (
                mock_webpdf_exporter_instance.allow_chromium_download is True
            )
