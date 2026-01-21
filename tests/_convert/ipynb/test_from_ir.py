from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.load import load_app
from marimo._convert.ipynb import convert_from_ir_to_ipynb
from marimo._convert.ipynb.from_ir import (
    _convert_marimo_output_to_ipynb,
    _maybe_extract_dataurl,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from tests.mocks import snapshotter

SELF_DIR = pathlib.Path(__file__).parent
snapshot_test = snapshotter(__file__)

pytest.importorskip("nbformat")


@pytest.mark.parametrize(
    "py_path", (SELF_DIR / "fixtures" / "py").glob("*.py")
)
def test_convert_from_ir_to_ipynb_snapshots(py_path: pathlib.Path) -> None:
    """Test convert_from_ir_to_ipynb against all Python fixtures using snapshots."""
    # Load the marimo app from file
    app = load_app(py_path)
    assert app
    internal_app = InternalApp(app)

    # Convert
    sort_mode = "top-down"
    ipynb_str = convert_from_ir_to_ipynb(internal_app, sort_mode=sort_mode)

    # Parse as JSON to validate and format consistently
    ipynb_json = json.loads(ipynb_str)
    formatted_ipynb = json.dumps(ipynb_json, indent=2, sort_keys=True)

    base_name = py_path.name.replace(".py", "")
    snapshot_name = f"{base_name}_{sort_mode.replace('-', '_')}.ipynb.txt"

    snapshot_test(snapshot_name, formatted_ipynb)


def test_export_ipynb_sort_modes() -> None:
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

    # Test top-down mode preserves document order
    content = convert_from_ir_to_ipynb(internal_app, sort_mode="top-down")
    snapshot_test("notebook_top_down.ipynb.txt", content)

    # Test topological mode respects dependencies
    content = convert_from_ir_to_ipynb(internal_app, sort_mode="topological")
    snapshot_test("notebook_topological.ipynb.txt", content)


@pytest.mark.parametrize(
    ("input_data", "expected"),
    [
        # Base64 data URL extraction
        (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
            "iVBORw0KGgoAAAANSUhEUgAAAAUA",
        ),
        # Non-data-URL string passes through
        ("hello world", "hello world"),
        # Dict passes through
        ({"key": "value"}, {"key": "value"}),
        # Int passes through
        (123, 123),
        # Data URL without base64 passes through
        ("data:text/plain,hello", "data:text/plain,hello"),
    ],
    ids=[
        "base64_data_url",
        "regular_string",
        "dict_passthrough",
        "int_passthrough",
        "data_url_no_base64",
    ],
)
def test_maybe_extract_dataurl(input_data: Any, expected: Any) -> None:
    """Test _maybe_extract_dataurl with various inputs."""
    result = _maybe_extract_dataurl(input_data)
    assert result == expected


@pytest.mark.parametrize(
    ("mimebundle", "expected_data", "expected_metadata"),
    [
        # Known mimetypes
        (
            {
                "text/plain": "Hello",
                "text/html": "<p>Hello</p>",
                "image/png": "data:image/png;base64,iVBORw0KGgo=",
            },
            {
                "text/plain": "Hello",
                "text/html": "<p>Hello</p>",
                "image/png": "iVBORw0KGgo=",
            },
            {},
        ),
        # Multiple formats
        (
            {
                "text/plain": "Figure(640x480)",
                "text/html": "<div>Chart</div>",
                "image/png": "data:image/png;base64,PNG_BASE64_DATA",
                "image/svg+xml": "<svg>...</svg>",
                "application/json": {"data": [1, 2, 3]},
            },
            {
                "text/plain": "Figure(640x480)",
                "text/html": "<div>Chart</div>",
                "image/png": "PNG_BASE64_DATA",
                "image/svg+xml": "<svg>...</svg>",
                "application/json": {"data": [1, 2, 3]},
            },
            {},
        ),
        # With metadata
        (
            {
                "text/plain": "Figure",
                "image/png": "PNG_DATA",
                "__metadata__": {"width": 640, "height": 480, "dpi": 100},
            },
            {"text/plain": "Figure", "image/png": "PNG_DATA"},
            {"width": 640, "height": 480, "dpi": 100},
        ),
        # Nested metadata
        (
            {
                "text/plain": "Figure",
                "image/png": "PNG_DATA",
                "__metadata__": {
                    "figure": {"width": 640, "height": 480},
                    "plot": {"type": "line", "color": "blue"},
                    "tags": ["important", "experiment-1"],
                },
            },
            {"text/plain": "Figure", "image/png": "PNG_DATA"},
            {
                "figure": {"width": 640, "height": 480},
                "plot": {"type": "line", "color": "blue"},
                "tags": ["important", "experiment-1"],
            },
        ),
    ],
    ids=[
        "known_mimetypes",
        "multiple_formats",
        "with_metadata",
        "nested_metadata",
    ],
)
def test_convert_marimo_mimebundle_to_ipynb(
    mimebundle: dict[str, Any],
    expected_data: dict[str, Any],
    expected_metadata: dict[str, Any],
) -> None:
    """Test marimo mimebundle conversion to ipynb format."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps(mimebundle),
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"] == expected_data
    assert result[0]["metadata"] == expected_metadata


def test_convert_marimo_mimebundle_with_non_dict_metadata() -> None:
    """Test that non-dict metadata is ignored."""
    mimebundle_data = json.dumps(
        {
            "text/plain": "Figure",
            "image/png": "PNG_DATA",
            "__metadata__": "not a dict",
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


def test_convert_marimo_mimebundle_empty() -> None:
    """Test that empty marimo mimebundle produces no output."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps({}),
    )

    result = _convert_marimo_output_to_ipynb(output, [])
    assert len(result) == 0


def test_convert_marimo_mimebundle_dict() -> None:
    """Handle the case when the mimebundle is a dict, not JSON-dumped string."""
    mimebundle_data = {
        "text/plain": "Figure",
        "image/png": "PNG_DATA",
        "__metadata__": {"width": 640, "height": 480},
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle_data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert "__metadata__" not in result[0]["data"]
    assert result[0]["data"]["text/plain"] == "Figure"
    assert result[0]["data"]["image/png"] == "PNG_DATA"
    assert result[0]["metadata"] == {"width": 640, "height": 480}


@pytest.mark.parametrize(
    ("mimetype", "data", "expected_data"),
    [
        # Data URL extraction
        (
            "image/png",
            "data:image/png;base64,REGULAR_PNG_DATA",
            {"image/png": "REGULAR_PNG_DATA"},
        ),
        # No data URL
        (
            "text/plain",
            "Hello World",
            {"text/plain": "Hello World"},
        ),
    ],
    ids=["with_dataurl", "without_dataurl"],
)
def test_convert_regular_output(
    mimetype: str, data: str, expected_data: dict[str, str]
) -> None:
    """Test regular output conversion."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype=mimetype,
        data=data,
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert len(result) == 1
    assert result[0]["output_type"] == "display_data"
    assert result[0]["data"] == expected_data
    assert result[0]["metadata"] == {}


def test_convert_console_outputs() -> None:
    """Test that console outputs (stdout/stderr) are converted correctly."""
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

    assert len(result) == 2
    assert result[0]["output_type"] == "stream"
    assert result[0]["name"] == "stdout"
    assert result[0]["text"] == "Console output\n"
    assert result[1]["output_type"] == "stream"
    assert result[1]["name"] == "stderr"
    assert result[1]["text"] == "Warning message\n"


def test_convert_marimo_mimebundle_with_both_output_and_console() -> None:
    """Test marimo mimebundle with both cell output and console outputs."""
    main_output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps({"text/plain": "Result", "image/png": "PNG_DATA"}),
    )

    console_outputs = [
        CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data="Console output\n",
        ),
    ]

    # Convert console outputs
    console_result = _convert_marimo_output_to_ipynb(None, console_outputs)
    # Convert main output
    main_result = _convert_marimo_output_to_ipynb(main_output, [])

    assert len(console_result) == 1
    assert console_result[0]["output_type"] == "stream"
    assert console_result[0]["name"] == "stdout"

    assert len(main_result) == 1
    assert main_result[0]["output_type"] == "display_data"
    assert main_result[0]["data"]["text/plain"] == "Result"
    assert main_result[0]["data"]["image/png"] == "PNG_DATA"
