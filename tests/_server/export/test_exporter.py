from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._messaging.notification import CellNotification
from marimo._server.export import (
    export_as_wasm,
    run_app_then_export_as_ipynb,
    run_app_until_completion,
)
from marimo._server.export.exporter import (
    Exporter,
    _convert_marimo_output_to_ipynb,
    _maybe_extract_dataurl,
)
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._session.notebook import AppFileManager
from marimo._session.state.session_view import SessionView
from marimo._utils.marimo_path import MarimoPath
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from pathlib import Path

snapshot = snapshotter(__file__)

HAS_NBFORMAT = DependencyManager.nbformat.has()


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_empty():
    app = App()
    internal_app = InternalApp(app)
    exporter = Exporter()

    content = exporter.export_as_ipynb(internal_app, sort_mode="top-down")
    snapshot("empty_notebook.ipynb.txt", content)


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_with_cells():
    app = App()

    @app.cell()
    def cell_1():
        print("hello")

    internal_app = InternalApp(app)
    exporter = Exporter()

    content = exporter.export_as_ipynb(internal_app, sort_mode="top-down")
    snapshot("notebook_with_cells.ipynb.txt", content)


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_sort_modes():
    app = App()

    @app.cell()
    def result(x, y):
        z = x + y
        return (z,)

    @app.cell()
    def __():
        x = 1
        return (x,)

    @app.cell()
    def __():
        y = 1
        return (y,)

    internal_app = InternalApp(app)
    exporter = Exporter()

    # Test top-down mode preserves document order
    content = exporter.export_as_ipynb(internal_app, sort_mode="top-down")
    snapshot("notebook_top_down.ipynb.txt", content)

    # Test topological mode respects dependencies
    content = exporter.export_as_ipynb(internal_app, sort_mode="topological")
    snapshot("notebook_topological.ipynb.txt", content)


HAS_DEPS = (
    HAS_NBFORMAT
    and DependencyManager.polars.has()
    and DependencyManager.altair.has()
    and DependencyManager.matplotlib.has()
)


# ruff: noqa: B018
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_export_ipynb_with_outputs(tmp_path: Path):
    app = App()

    # stdout
    @app.cell()
    def __():
        print("hello")
        return

    # # stdout
    # @app.cell()
    # def cell_2():
    #     import sys

    #     sys.stdout.write("world\n")
    #     return (sys,)

    # # stderr
    # @app.cell()
    # def cell_3(sys):
    #     sys.stderr.write("error\n")
    #     return ()

    # This includes the filepath in the error message, which is not
    # good for snapshots
    # @app.cell()
    # def cell_3():
    #     raise Exception("error")
    #     return ()

    # display
    @app.cell(hide_code=True)
    def cell_4():
        x = 10
        return (x,)

    # disabled
    @app.cell(disabled=True)
    def __():
        print("disabled")
        return

    # dependency
    @app.cell()
    def cell_5(x):
        y = x + 1
        y * 2
        return (y,)

    # dependency
    @app.cell()
    def cell_6():
        import marimo as mo

        return (mo,)

    # pure markdown
    @app.cell()
    def cell_7(mo):
        mo.md("hello")
        return ()

    # interpolated markdown
    @app.cell()
    def cell_8(mo, x):
        mo.md(f"hello {x}")
        return ()

    # # polars
    # @app.cell()
    # def cell_9():
    #     import polars as pl

    #     df = pl.DataFrame({"a": [1, 2, 3]})
    #     df
    #     return (df,)

    # mo.ui.table
    # @app.cell()
    # def cell_10(df, mo):
    #     mo.ui.table(df)
    #     return ()

    # slider
    @app.cell()
    def cell_11(mo):
        mo.ui.slider(start=0, stop=10)
        return ()

    # hstack
    @app.cell()
    def cell_12(mo):
        mo.vstack([mo.md("hello"), mo.md("world")])
        return ()

    # # altair chart
    # @app.cell()
    # def cell_13(df):
    #     import altair as alt

    #     chart = alt.Chart(df).mark_point().encode(x="a")
    #     chart
    #     return (chart,)

    # # matplotlib
    # @app.cell()
    # def cell_14():
    #     import matplotlib.pyplot as plt

    #     plt.plot([1, 2])
    #     return (plt,)

    internal_app = InternalApp(app)
    exporter = Exporter()

    content = exporter.export_as_ipynb(
        internal_app, sort_mode="top-down", session_view=None
    )
    assert content is not None

    test_file = tmp_path / "notebook.py"
    test_file.write_text(InternalApp(app).to_py())

    result = await run_app_then_export_as_ipynb(
        MarimoPath(test_file),
        sort_mode="top-down",
        cli_args={},
        argv=None,
    )
    assert not result.did_error
    assert result.download_filename == "notebook.ipynb"
    snapshot("notebook_with_outputs.ipynb.txt", result.contents)


async def test_run_until_completion_with_stop():
    app = App()

    @app.cell()
    def cell_1():
        import marimo as mo

        return (mo,)

    @app.cell()
    def cell_2(mo):
        mo.stop(True)
        x = 10
        return (x,)

    @app.cell()
    def cell_3(x):
        y = x + 1
        y
        return (y,)

    file_manager = AppFileManager.from_app(InternalApp(app))

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
async def test_run_until_completion_with_stack_trace():
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

    # When not redirected, the stack trace is not included in the output
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
        _delete_lines_with_files(messages),
    )


async def test_export_wasm_edit():
    app = App()

    @app.cell()
    def cell_1():
        print("hello wasm")
        return

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_wasm(
        filename=file_manager.filename,
        app=file_manager.app,
        display_config=DEFAULT_CONFIG["display"],
        mode="edit",
        code=file_manager.app.to_py(),
        show_code=True,
    )

    assert filename == "notebook.wasm.html"
    assert "alert(" in content
    assert '"mode": "edit"' in content


async def test_export_wasm_run():
    app = App()

    @app.cell()
    def cell_1():
        print("hello wasm")
        return

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_wasm(
        filename=file_manager.filename,
        app=file_manager.app,
        display_config=DEFAULT_CONFIG["display"],
        mode="run",
        code=file_manager.app.to_py(),
        show_code=True,
    )

    assert filename == "notebook.wasm.html"
    assert "alert(" in content
    assert '"mode": "read"' in content


async def test_export_html_with_layout(tmp_path: Path):
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """
import marimo

app = marimo.App(layout_file="layouts/layout.json")

@app.cell()
def __():
    x = 1
    return
"""
    )

    # Create the layout file
    layout_file = tmp_path / "layouts" / "layout.json"
    layout_file.parent.mkdir(parents=True, exist_ok=True)
    layout_file.write_text('{"type": "slides", "data": {}}')

    # Export the app
    result = export_as_wasm(
        path=MarimoPath(test_file),
        mode="edit",
        show_code=True,
    )
    assert result.did_error is False
    assert "layout.json" not in result.contents
    assert "data:application/json" in result.contents


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


def _delete_lines_with_files(output: str) -> str:
    # Remove any line that contains "File " up until a .py ending
    def remove_file_name(line: str) -> str:
        if "File " not in line:
            return line
        start = line.index("File ")
        end = line.rindex(".py") + 3
        return line[0:start] + line[end:]

    return "\n".join(remove_file_name(line) for line in output.splitlines())


@patch("marimo._server.export.echo")
async def test_run_until_completion_with_console_output(mock_echo: MagicMock):
    app = App()

    @app.cell()
    def _():
        sys.stdout.write("hello stdout")
        None
        return

    @app.cell()
    def _():
        import sys

        sys.stderr.write("hello stderr")
        None
        return (sys,)

    file_manager = AppFileManager.from_app(InternalApp(app))

    session_view, did_error = await run_app_until_completion(
        file_manager,
        cli_args={},
        argv=None,
    )
    assert did_error is False

    def _assert_contents():
        # File should be sys.stderr, but it can change during CI execution
        # So, we use ANY for the file parameter.
        mock_echo.assert_any_call("hello stdout", file=ANY, nl=False)
        mock_echo.assert_any_call("hello stderr", file=ANY, nl=False)

    n_tries = 0
    limit = 10
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


def test_export_as_html_with_serialization(session_view: SessionView):
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


def test_export_as_html_without_code(session_view: SessionView):
    """Test HTML export clears code when include_code=False."""
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
        "secret_value = 'should_not_appear'\nprint('visible output')\nreturn secret_value"
    )

    exporter = Exporter()

    request = ExportAsHTMLRequest(
        download=False,
        files=[],
        include_code=False,
    )

    html, filename = exporter.export_as_html(
        filename=file_manager.filename,
        app=file_manager.app,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    # Code should not appear in the HTML
    assert "secret_value" not in html
    assert "should_not_appear" not in html

    # But outputs should still be visible
    assert "visible output" in html

    # Console outputs should be cleared (no console message in HTML)
    # The exact format depends on template implementation


def test_export_as_html_with_files(session_view: SessionView):
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
        files=["/@file/10-test.txt"],  # Mock file reference
        include_code=True,
    )

    # Mock the read_virtual_file function to avoid file system dependencies
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
    # Files should be embedded as data URLs
    assert "data:" in html


def test_export_as_html_with_cell_configs(session_view: SessionView):
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
    # Verify that the serialized notebook data contains configuration
    assert (
        "hide_code" in html or "hideCode" in html
    )  # depends on serialization format
    assert "configured" in html


def test_export_as_html_preserves_output_order(session_view: SessionView):
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

    # Add cells in different order than execution
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
    # All outputs should be present
    assert "output_0" in html
    assert "output_1" in html
    assert "output_2" in html


def test_export_as_html_with_error_outputs(session_view: SessionView):
    """Test HTML export handles error outputs correctly."""
    app = App()

    @app.cell()
    def error_cell():
        raise ValueError("Test error")

    file_manager = AppFileManager.from_app(InternalApp(app))

    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    # Mock an error output
    from marimo._messaging.errors import MarimoExceptionRaisedError

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
    # Error should be serialized in the session snapshot
    assert "Test error" in html or "ValueError" in html


def test_export_as_html_code_hash_consistency(session_view: SessionView):
    """Test HTML export includes correct code hash regardless of include_code setting."""
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

    # Both should contain the same code hash
    # The code hash should be in both because it's computed from the actual file code
    import re

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

    # Verify that when include_code=False, the notebook cells have empty code
    assert '"code": ""' in html_without_code, (
        "Cell code should be empty when include_code=False"
    )
    # But when include_code=True, the notebook cells should have code
    assert '"code": "return' in html_with_code, (
        "Cell code should be present when include_code=True"
    )


def test_export_html_replaces_virtual_files_in_outputs(
    session_view: SessionView,
):
    """Test that virtual file URLs in HTML outputs are replaced with data URIs."""
    app = App()

    @app.cell()
    def test_cell():
        import marimo as mo

        return mo.image(src="test.png")

    file_manager = AppFileManager.from_app(InternalApp(app))

    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    # Create HTML output with a virtual file reference
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

    # Include the virtual file in request.files
    # Note: request.files uses /@file/ format (without the ./)
    request = ExportAsHTMLRequest(
        download=True,
        files=["/@file/100-test.png"],
        include_code=True,
    )

    # Mock read_virtual_file to return test image data
    with patch(
        "marimo._server.export.dom_traversal.read_virtual_file"
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

    # Virtual file should be replaced with data URI in the output
    assert "./@file/100-test.png" not in html
    assert "data:image/png;base64," in html

    # Verify the base64-encoded data is present (fake_image_data)
    import base64

    expected_b64 = base64.b64encode(b"fake_image_data").decode()
    assert expected_b64 in html


def test_export_html_replaces_multiple_virtual_files_complex(
    session_view: SessionView,
):
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
        # Cell with both virtual file and external URL
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
        'return \'<div><img src="./@file/300-diagram.svg"><img src="https://example.com/external.png"></div>\''
    )

    exporter = Exporter()

    # Include all virtual files plus an extra one not in outputs
    # Note: request.files uses /@file/ format (without the ./)
    request = ExportAsHTMLRequest(
        download=True,
        files=[
            "/@file/100-chart.png",
            "/@file/200-plot.png",
            "/@file/300-diagram.svg",
            "/@file/400-unused.txt",  # Not in any output
        ],
        include_code=True,
    )

    # Mock read_virtual_file
    def mock_read_side_effect(filename: str, byte_length: int) -> bytes:
        """Return different mock data based on filename."""
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
            "marimo._server.export.dom_traversal.read_virtual_file"
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

    # Verify base64-encoded data is present for replaced files
    import base64

    chart_b64 = base64.b64encode(b"chart_data").decode()
    plot_b64 = base64.b64encode(b"plot_data").decode()
    diagram_b64 = base64.b64encode(b"<svg>diagram</svg>").decode()

    # At least some of the base64 data should be in the HTML
    # (virtual files are replaced with data URIs)
    assert chart_b64 in html, "Chart data should be embedded as base64"
    assert plot_b64 in html, "Plot data should be embedded as base64"
    assert diagram_b64 in html, "Diagram data should be embedded as base64"

    # Data URIs should be present
    assert "data:image/png;base64," in html  # For chart and plot
    assert "data:image/svg+xml;base64," in html  # For diagram

    # External URL should remain unchanged
    assert "https://example.com/external.png" in html

    # Virtual file URLs should be replaced (though they may be URL-encoded in JSON)
    # So we just check that the base64 data is present, which proves replacement worked


# Tests for marimo mimebundle ipynb export support


def test_maybe_extract_dataurl_with_base64_data():
    """Test that _maybe_extract_dataurl extracts base64 data from data URLs."""
    data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
    result = _maybe_extract_dataurl(data_url)
    assert result == "iVBORw0KGgoAAAANSUhEUgAAAAUA"


def test_maybe_extract_dataurl_without_base64():
    """Test that _maybe_extract_dataurl returns non-data-URL strings as-is."""
    regular_string = "hello world"
    result = _maybe_extract_dataurl(regular_string)
    assert result == "hello world"


def test_maybe_extract_dataurl_with_non_string():
    """Test that _maybe_extract_dataurl returns non-string data as-is."""
    data = {"key": "value"}
    result = _maybe_extract_dataurl(data)
    assert result == {"key": "value"}

    data = 123
    result = _maybe_extract_dataurl(data)
    assert result == 123


def test_maybe_extract_dataurl_with_data_prefix_but_no_base64():
    """Test that _maybe_extract_dataurl handles data: prefix without base64."""
    data_url = "data:text/plain,hello"
    result = _maybe_extract_dataurl(data_url)
    assert result == "data:text/plain,hello"


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_to_ipynb_with_known_mimetypes():
    """Test that marimo mimebundle with known mimetypes are converted correctly."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Hello",
            "text/html": "<p>Hello</p>",
            "image/png": "data:image/png;base64,iVBORw0KGgo=",
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert "text/plain" in result[0]["data"]
    assert result[0]["data"]["text/plain"] == "Hello"
    assert "text/html" in result[0]["data"]
    assert result[0]["data"]["text/html"] == "<p>Hello</p>"
    assert "image/png" in result[0]["data"]
    # Base64 data should be extracted from data URL
    assert result[0]["data"]["image/png"] == "iVBORw0KGgo="


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_multiple_formats():
    """Test marimo mimebundle with multiple output formats."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure(640x480)",
            "text/html": "<div>Chart</div>",
            "image/png": "data:image/png;base64,PNG_BASE64_DATA",
            "image/svg+xml": "<svg>...</svg>",
            "application/json": {"data": [1, 2, 3]},
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["text/plain"] == "Figure(640x480)"
    assert result[0]["data"]["text/html"] == "<div>Chart</div>"
    assert result[0]["data"]["image/png"] == "PNG_BASE64_DATA"
    assert result[0]["data"]["image/svg+xml"] == "<svg>...</svg>"
    assert result[0]["data"]["application/json"] == {"data": [1, 2, 3]}


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_regular_output_extracts_dataurl():
    """Test that regular outputs also extract data URLs."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="image/png",
        data="data:image/png;base64,REGULAR_PNG_DATA",
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["image/png"] == "REGULAR_PNG_DATA"


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_regular_output_without_dataurl():
    """Test that regular outputs without data URLs are passed through."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="text/plain",
        data="Hello World",
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["text/plain"] == "Hello World"


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_empty():
    """Test that empty marimo mimebundle produces no output."""
    mimebundle_data = json.dumps({})

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    # Empty mimebundle should not produce any output
    assert len(result) == 0


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_console_output():
    """Test that console outputs (stdout/stderr) are converted correctly."""
    # Test just console outputs without main output
    console_outputs = [
        CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data="Console output\n",
        ),
        CellOutput(
            channel=CellChannel.STDERR,
            mimetype="text/plain",
            data="Warning message\n",
        ),
    ]

    result = _convert_marimo_output_to_ipynb(None, console_outputs)

    # Should have stdout and stderr outputs
    assert len(result) == 2
    assert result[0]["output_type"] == "stream"
    assert result[0]["name"] == "stdout"
    assert result[0]["text"] == "Console output\n"
    assert result[1]["output_type"] == "stream"
    assert result[1]["name"] == "stderr"
    assert result[1]["text"] == "Warning message\n"


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_both_output_and_console():
    """Test marimo mimebundle with both cell output and console outputs."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Result",
            "image/png": "PNG_DATA",
        }
    )

    main_output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    console_outputs = [
        CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data="Console output\n",
        ),
    ]

    # First convert console outputs
    console_result = _convert_marimo_output_to_ipynb(None, console_outputs)
    # Then convert main output
    main_result = _convert_marimo_output_to_ipynb(main_output, [])

    # Verify console output
    assert len(console_result) == 1
    assert console_result[0]["output_type"] == "stream"
    assert console_result[0]["name"] == "stdout"

    # Verify main output
    assert len(main_result) == 1
    assert main_result[0]["output_type"] == "display_data"
    assert main_result[0]["data"]["text/plain"] == "Result"
    assert main_result[0]["data"]["image/png"] == "PNG_DATA"


# Tests for metadata in ipynb export


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_metadata():
    """Test that metadata from __metadata__ key is included in ipynb output."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
            "__metadata__": {
                "width": 640,
                "height": 480,
                "dpi": 100,
            },
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["text/plain"] == "Figure"
    assert result[0]["data"]["image/png"] == "PNG_DATA"
    # Verify metadata is included
    assert "metadata" in result[0]
    assert result[0]["metadata"] == {
        "width": 640,
        "height": 480,
        "dpi": 100,
    }


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_without_metadata():
    """Test that outputs without metadata have empty metadata dict."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["text/plain"] == "Figure"
    assert result[0]["data"]["image/png"] == "PNG_DATA"
    # Verify metadata is empty
    assert "metadata" in result[0]
    assert result[0]["metadata"] == {}


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_non_dict_metadata():
    """Test that non-dict metadata is ignored."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
            "__metadata__": "not a dict",  # This should be ignored
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    # Verify metadata is empty when non-dict value is provided
    assert "metadata" in result[0]
    assert result[0]["metadata"] == {}


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_with_nested_metadata():
    """Test that nested metadata structures are preserved."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
            "__metadata__": {
                "figure": {
                    "width": 640,
                    "height": 480,
                },
                "plot": {
                    "type": "line",
                    "color": "blue",
                },
                "tags": ["important", "experiment-1"],
            },
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    # Verify nested metadata is preserved
    assert result[0]["metadata"] == {
        "figure": {
            "width": 640,
            "height": 480,
        },
        "plot": {
            "type": "line",
            "color": "blue",
        },
        "tags": ["important", "experiment-1"],
    }


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_metadata_not_in_data():
    """Test that __metadata__ key is not included in output data."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
            "__metadata__": {
                "width": 640,
                "height": 480,
            },
        }
    )

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    # Verify __metadata__ is not in the data dict
    assert "__metadata__" not in result[0]["data"]
    assert "text/plain" in result[0]["data"]
    assert "image/png" in result[0]["data"]
    # But metadata should be in the metadata field
    assert result[0]["metadata"] == {
        "width": 640,
        "height": 480,
    }


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_marimo_mimebundle_dict():
    """Handle the case when the mimebundle is a dict, not JSON-dumped string"""
    mimebundle_data = {
        "text/plain": "Figure",
        "image/png": "PNG_DATA",
        "__metadata__": {
            "width": 640,
            "height": 480,
        },
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    # Verify __metadata__ is not in the data dict
    assert "__metadata__" not in result[0]["data"]
    assert "text/plain" in result[0]["data"]
    assert "image/png" in result[0]["data"]
    # But metadata should be in the metadata field
    assert result[0]["metadata"] == {
        "width": 640,
        "height": 480,
    }


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_convert_regular_output_has_empty_metadata():
    """Test that regular outputs (non-mimebundle) have empty metadata."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="text/plain",
        data="Hello World",
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"]["text/plain"] == "Hello World"
    # Regular outputs should have empty metadata
    assert "metadata" in result[0]
    assert result[0]["metadata"] == {}
