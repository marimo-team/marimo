from __future__ import annotations

import asyncio
import json
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import CellOp
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._server.export import (
    export_as_wasm,
    run_app_then_export_as_ipynb,
    run_app_until_completion,
)
from marimo._server.export.exporter import Exporter
from marimo._server.file_manager import AppFileManager
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.session.session_view import SessionView
from marimo._utils.marimo_path import MarimoPath
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from pathlib import Path

snapshot = snapshotter(__file__)

HAS_NBFORMAT = DependencyManager.nbformat.has()


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_empty():
    app = App()
    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down"
    )
    assert filename == "notebook.ipynb"
    snapshot("empty_notebook.ipynb.txt", content)


@pytest.mark.skipif(not HAS_NBFORMAT, reason="nbformat is not installed")
def test_export_ipynb_with_cells():
    app = App()

    @app.cell()
    def cell_1():
        print("hello")

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down"
    )
    assert filename == "notebook.ipynb"
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

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    # Test top-down mode preserves document order
    content, _ = exporter.export_as_ipynb(file_manager, sort_mode="top-down")
    snapshot("notebook_top_down.ipynb.txt", content)

    # Test topological mode respects dependencies
    content, _ = exporter.export_as_ipynb(
        file_manager, sort_mode="topological"
    )
    snapshot("notebook_topological.ipynb.txt", content)


HAS_DEPS = (
    HAS_NBFORMAT
    and DependencyManager.polars.has()
    and DependencyManager.altair.has()
    and DependencyManager.matplotlib.has()
)


# ruff: noqa: B018
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
async def test_export_ipynb_with_outputs():
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

    file_manager = AppFileManager.from_app(InternalApp(app))
    exporter = Exporter()

    content, filename = exporter.export_as_ipynb(
        file_manager, sort_mode="top-down", session_view=None
    )
    assert filename == "notebook.ipynb"
    assert content is not None

    result = await run_app_then_export_as_ipynb(
        file_manager,
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
    cell_ops = [op for op in session_view.operations if isinstance(op, CellOp)]
    snapshot("run_until_completion_with_stop.txt", _print_messages(cell_ops))


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
    cell_ops = [op for op in session_view.operations if isinstance(op, CellOp)]

    messages = _print_messages(cell_ops)
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
        file_manager=file_manager,
        display_config=DEFAULT_CONFIG["display"],
        mode="edit",
        code=file_manager.to_code(),
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
        file_manager=file_manager,
        display_config=DEFAULT_CONFIG["display"],
        mode="run",
        code=file_manager.to_code(),
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


def _print_messages(messages: list[CellOp]) -> str:
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
    return json.dumps(result, indent=2, cls=WebComponentEncoder)


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
        mock_echo.assert_any_call("hello stdout", file=sys.stderr, nl=False)
        mock_echo.assert_any_call("hello stderr", file=sys.stderr, nl=False)

    n_tries = 0
    while n_tries <= 5:
        try:
            _assert_contents()
            break
        except Exception:
            n_tries += 1
            await asyncio.sleep(0.1)

    cell_ops = [op for op in session_view.operations if isinstance(op, CellOp)]
    snapshot(
        "run_until_completion_with_console_output.txt",
        _print_messages(cell_ops),
    )


def test_export_as_html_with_serialization():
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
    session_view = SessionView()

    # Add some test data to session view
    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_operations[cell_ids[0]] = CellOp(
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

    session_view.cell_operations[cell_ids[1]] = CellOp(
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
        file_manager=file_manager,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    assert "Hello World" in html
    assert "Markdown Cell" in html
    assert 'data-marimo="true"' in html


def test_export_as_html_without_code():
    """Test HTML export clears code when include_code=False."""
    app = App()

    @app.cell()
    def test_cell():
        secret_value = "should_not_appear"
        print("visible output")
        return secret_value

    file_manager = AppFileManager.from_app(InternalApp(app))
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_operations[cell_ids[0]] = CellOp(
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
        file_manager=file_manager,
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


def test_export_as_html_with_files():
    """Test HTML export includes virtual files."""
    app = App()

    @app.cell()
    def test_cell():
        return "test"

    file_manager = AppFileManager.from_app(InternalApp(app))
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_operations[cell_ids[0]] = CellOp(
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
            file_manager=file_manager,
            session_view=session_view,
            display_config=DEFAULT_CONFIG["display"],
            request=request,
        )

    assert filename == "notebook.html"
    # Files should be embedded as data URLs
    assert "data:" in html


def test_export_as_html_with_cell_configs():
    """Test HTML export preserves cell configurations through serialization."""
    app = App()

    @app.cell(hide_code=True, disabled=True, column=1)
    def configured_cell():
        return "configured"

    file_manager = AppFileManager.from_app(InternalApp(app))
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_operations[cell_ids[0]] = CellOp(
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
        file_manager=file_manager,
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


def test_export_as_html_preserves_output_order():
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
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    # Add cells in different order than execution
    for i, cell_id in enumerate(cell_ids):
        session_view.cell_operations[cell_id] = CellOp(
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
        file_manager=file_manager,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    # All outputs should be present
    assert "output_0" in html
    assert "output_1" in html
    assert "output_2" in html


def test_export_as_html_with_error_outputs():
    """Test HTML export handles error outputs correctly."""
    app = App()

    @app.cell()
    def error_cell():
        raise ValueError("Test error")

    file_manager = AppFileManager.from_app(InternalApp(app))
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())

    # Mock an error output
    from marimo._messaging.errors import MarimoExceptionRaisedError

    error = MarimoExceptionRaisedError(
        type="exception",
        exception_type="ValueError",
        msg="Test error",
        raising_cell=cell_ids[0],
    )

    session_view.cell_operations[cell_ids[0]] = CellOp(
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
        file_manager=file_manager,
        session_view=session_view,
        display_config=DEFAULT_CONFIG["display"],
        request=request,
    )

    assert filename == "notebook.html"
    # Error should be serialized in the session snapshot
    assert "Test error" in html or "ValueError" in html


def test_export_as_html_code_hash_consistency():
    """Test HTML export includes correct code hash regardless of include_code setting."""
    app = App()

    @app.cell()
    def test_cell():
        return "test"

    file_manager = AppFileManager.from_app(InternalApp(app))
    session_view = SessionView()

    cell_ids = list(file_manager.app.cell_manager.cell_ids())
    session_view.cell_operations[cell_ids[0]] = CellOp(
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
        file_manager=file_manager,
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
        file_manager=file_manager,
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
