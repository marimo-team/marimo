from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.load import load_app
from marimo._convert.ipynb import convert_from_ir_to_ipynb
from marimo._convert.ipynb.from_ir import (
    _clean_ansi_for_export,
    _convert_latex_delimiters_for_jupyter,
    _convert_marimo_output_to_ipynb,
    _convert_marimo_tex_to_latex,
    _is_marimo_component,
    _maybe_extract_dataurl,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._output.md import _md
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
        # SVG string from Base64 data URL
        (
            "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
            "<svg></svg>",
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
        "svg_string_from_base64_data_url",
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
    assert result == [
        {
            "output_type": "display_data",
            "metadata": expected_metadata,
            "data": expected_data,
        }
    ]


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
    assert (
        result
        == [
            {
                "output_type": "display_data",
                "metadata": {},  # Verify metadata is empty when non-dict value is provided
                "data": {
                    "text/plain": "Figure",
                    "image/png": "PNG_DATA",
                    "__metadata__": "not a dict",
                },
            }
        ]
    )


def test_convert_marimo_mimebundle_empty() -> None:
    """Test that empty marimo mimebundle produces no output."""
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps({}),
    )

    result = _convert_marimo_output_to_ipynb(output, [])
    assert result == []


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

    assert result == [
        {
            "output_type": "display_data",
            "metadata": {"width": 640, "height": 480},
            "data": {"text/plain": "Figure", "image/png": "PNG_DATA"},
        }
    ]


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

    assert result == [
        {
            "output_type": "display_data",
            "metadata": {},
            "data": expected_data,
        }
    ]


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
    assert result == [
        {
            "output_type": "stream",
            "name": "stdout",
            "text": "Console output\n",
        },
        {
            "output_type": "stream",
            "name": "stderr",
            "text": "Warning message\n",
        },
    ]


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

    assert console_result == [
        {
            "output_type": "stream",
            "name": "stdout",
            "text": "Console output\n",
        }
    ]

    assert main_result == [
        {
            "output_type": "display_data",
            "metadata": {},
            "data": {
                "text/plain": "Result",
                "image/png": "PNG_DATA",
            },
        }
    ]


@pytest.mark.parametrize(
    ("html_content", "expected"),
    [
        # Marimo components should be detected
        ("<marimo-plotly data-figure='{}'>", True),
        ("<marimo-table data-data='[]'>", True),
        ("<marimo-slider value='5'>", True),
        ('<marimo-output data-output="test">', True),
        # List of strings (as Jupyter stores text/html)
        (["<marimo-plotly data-figure='{}'>"], True),
        (["<div>", "<marimo-chart>", "</div>"], True),
        # Regular HTML should not be detected
        ("<div>Hello World</div>", False),
        ("<p>Some <b>text</b></p>", False),
        ("<script>console.log('test')</script>", False),
        # Edge cases
        ("", False),
        ("marimo-plotly", False),  # Not an HTML tag
        ("<div>marimo-test</div>", False),  # Not a marimo tag
        # Non-string types
        (123, False),
        (None, False),
        ({"key": "value"}, False),
    ],
    ids=[
        "marimo_plotly",
        "marimo_table",
        "marimo_slider",
        "marimo_output",
        "list_with_marimo",
        "list_marimo_nested",
        "regular_div",
        "regular_paragraph",
        "regular_script",
        "empty_string",
        "marimo_text_not_tag",
        "marimo_in_text_not_tag",
        "integer",
        "none",
        "dict",
    ],
)
def test_is_marimo_component(html_content: Any, expected: bool) -> None:
    """Test _is_marimo_component detection of marimo custom elements."""
    assert _is_marimo_component(html_content) == expected


def test_convert_mimebundle_filters_marimo_components() -> None:
    """Test that marimo components in text/html are filtered out of mimebundle."""
    # Mimebundle with marimo-plotly HTML and PNG fallback
    mimebundle = {
        "text/html": "<marimo-plotly data-figure='{\"data\": []}'>",
        "image/png": "data:image/png;base64,iVBORw0KGgo=",
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps(mimebundle),
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    # text/html should be filtered out because it contains a marimo component
    assert result == [
        {
            "output_type": "display_data",
            "data": {
                "image/png": "iVBORw0KGgo="
            },  # image/png should remain (with data URL prefix stripped)
            "metadata": {},
        }
    ]


def test_convert_mimebundle_keeps_regular_html() -> None:
    """Test that regular HTML is preserved in mimebundle."""
    mimebundle = {
        "text/html": "<div><p>Regular HTML content</p></div>",
        "image/png": "PNG_DATA",
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps(mimebundle),
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert result == [
        {
            "output_type": "display_data",
            "data": {
                "text/html": "<div><p>Regular HTML content</p></div>",
                "image/png": "PNG_DATA",
            },
            "metadata": {},
        }
    ]


def test_convert_mimebundle_marimo_component_only_png_remains() -> None:
    """Test mimebundle with only marimo HTML and PNG produces only PNG output."""
    mimebundle = {
        "text/html": ["<marimo-table data-data='[]'>"],  # List format
        "image/png": "VALID_PNG_DATA",
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=mimebundle,  # Dict format, not JSON string
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert result == [
        {
            "output_type": "display_data",
            "data": {"image/png": "VALID_PNG_DATA"},
            "metadata": {},
        }
    ]


def test_convert_mimebundle_marimo_component_preserves_other_mimes() -> None:
    """Test that filtering marimo HTML preserves other MIME types."""
    mimebundle = {
        "text/html": "<marimo-slider value='5'>",
        "text/plain": "Slider(value=5)",
        "image/png": "PNG_DATA",
        "application/json": {"value": 5},
    }

    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="application/vnd.marimo+mimebundle",
        data=json.dumps(mimebundle),
    )

    result = _convert_marimo_output_to_ipynb(output, [])

    assert result == [
        {
            "output_type": "display_data",
            "data": {
                "text/plain": "Slider(value=5)",
                "image/png": "PNG_DATA",
                "application/json": {"value": 5},
            },
            "metadata": {},
        }
    ]


def test_convert_console_media_output() -> None:
    """Test that MEDIA channel console outputs (e.g., plt.show()) are converted."""
    console_outputs = [
        CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data="Before plot\n",
        ),
        CellOutput(
            channel=CellChannel.MEDIA,
            mimetype="application/vnd.marimo+mimebundle",
            data={
                "text/plain": "<Figure size 640x480 with 1 Axes>",
                "image/png": "data:image/png;base64,iVBORw0KGgo=",
            },
        ),
        CellOutput(
            channel=CellChannel.STDOUT,
            mimetype="text/plain",
            data="After plot\n",
        ),
    ]

    result = _convert_marimo_output_to_ipynb(None, console_outputs)

    assert result == [
        {
            "output_type": "stream",
            "name": "stdout",
            "text": "Before plot\n",
        },
        {
            "output_type": "display_data",
            "metadata": {},
            "data": {
                "text/plain": "<Figure size 640x480 with 1 Axes>",
                "image/png": "iVBORw0KGgo=",  # Base64 extracted
            },
        },
        {
            "output_type": "stream",
            "name": "stdout",
            "text": "After plot\n",
        },
    ]


def test_convert_console_media_with_marimo_component() -> None:
    """Test that marimo components in console MEDIA outputs are filtered."""
    console_outputs = [
        CellOutput(
            channel=CellChannel.MEDIA,
            mimetype="application/vnd.marimo+mimebundle",
            data={
                "text/html": "<marimo-plotly data-figure='{}'>",
                "image/png": "PNG_FALLBACK_DATA",
            },
        ),
    ]

    result = _convert_marimo_output_to_ipynb(None, console_outputs)

    # Marimo component HTML should be filtered, PNG should remain
    assert result == [
        {
            "output_type": "display_data",
            "metadata": {},
            "data": {"image/png": "PNG_FALLBACK_DATA"},
        }
    ]


def test_convert_console_output_channel() -> None:
    """Test that OUTPUT channel console outputs are also handled."""
    console_outputs = [
        CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="image/png",
            data="data:image/png;base64,CONSOLE_PNG_DATA",
        ),
    ]

    result = _convert_marimo_output_to_ipynb(None, console_outputs)

    assert result == [
        {
            "output_type": "display_data",
            "metadata": {},
            "data": {"image/png": "CONSOLE_PNG_DATA"},
        }
    ]


class TestCleanAnsiForExport:
    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            # Plain text passes through unchanged
            ("Hello World", "Hello World"),
            ("", ""),
            # Standard ANSI color codes are preserved (for nbconvert's template)
            ("\x1b[34mBlue text\x1b[0m", "\x1b[34mBlue text\x1b[0m"),
            (
                "\x1b[31mRed\x1b[0m and \x1b[32mGreen\x1b[0m",
                "\x1b[31mRed\x1b[0m and \x1b[32mGreen\x1b[0m",
            ),
            # Character set selection sequences ARE stripped (cause LaTeX errors)
            ("\x1b(B", ""),
            ("\x1b)B", ""),
            ("\x1b(A", ""),
            ("\x1b(0", ""),
            # Mixed: color codes preserved, character set sequences stripped
            (
                "\x1b[34m[D 260124 22:51:42 cell_runner:711]\x1b(B\x1b[m Running",
                "\x1b[34m[D 260124 22:51:42 cell_runner:711]\x1b[m Running",
            ),
            # Multiple character set sequences stripped
            ("\x1b(B\x1b[34mText\x1b(B\x1b[0m\x1b)A", "\x1b[34mText\x1b[0m"),
        ],
        ids=[
            "plain_text",
            "empty_string",
            "single_color",
            "multiple_colors",
            "charset_paren_b",
            "charset_close_b",
            "charset_paren_a",
            "charset_paren_0",
            "marimo_logger_output",
            "multiple_charset_sequences",
        ],
    )
    def test_clean_ansi_for_export(
        self, input_text: str, expected: str
    ) -> None:
        """Test _clean_ansi_for_export with various ANSI sequences."""
        result = _clean_ansi_for_export(input_text)
        assert result == expected

    def test_clean_ansi_for_export_non_string(self) -> None:
        """Test _clean_ansi_for_export with non-string inputs."""
        assert _clean_ansi_for_export({"key": "value"}) == "{'key': 'value'}"
        assert _clean_ansi_for_export([1, 2, 3]) == "[1, 2, 3]"
        assert _clean_ansi_for_export(None) == "None"
        assert _clean_ansi_for_export(123) == "123"

    def test_console_output_with_ansi_cleaned(self) -> None:
        """Test console output conversion cleans ANSI sequences."""
        # Simulated marimo logger output with problematic \x1b(B sequence
        raw_log = "\x1b[34m[D 260124 22:51:42 cell_runner:711]\x1b(B\x1b[m Test message\n"

        console_outputs = [
            CellOutput(
                channel=CellChannel.STDERR,
                mimetype="text/plain",
                data=raw_log,
            ),
        ]

        result = _convert_marimo_output_to_ipynb(None, console_outputs)

        assert result == [
            {
                "output_type": "stream",
                "name": "stderr",
                "text": "\x1b[34m[D 260124 22:51:42 cell_runner:711]\x1b[m Test message\n",
            }
        ]

    def test_console_outputs_multiple_with_ansi(self) -> None:
        """Test multiple console outputs with ANSI codes are all cleaned."""
        console_outputs = [
            CellOutput(
                channel=CellChannel.STDOUT,
                mimetype="text/plain",
                data="\x1b[32m[I log]\x1b(B\x1b[m stdout message\n",
            ),
            CellOutput(
                channel=CellChannel.STDERR,
                mimetype="text/plain",
                data="\x1b[34m[D log]\x1b(B\x1b[m stderr message\n",
            ),
        ]

        result = _convert_marimo_output_to_ipynb(None, console_outputs)

        assert result == [
            {
                "output_type": "stream",
                "name": "stdout",
                "text": "\x1b[32m[I log]\x1b[m stdout message\n",
            },
            {
                "output_type": "stream",
                "name": "stderr",
                "text": "\x1b[34m[D log]\x1b[m stderr message\n",
            },
        ]

    @pytest.mark.skip(
        reason="This test can take some time and requires some libraries like xelatex, useful for local testing"
    )
    def test_clean_ansi_does_not_crash_pdf_export(self) -> None:
        """Integration test: verify cleaned output doesn't crash nbconvert PDF export."""
        pytest.importorskip("nbconvert")
        import nbformat
        from nbconvert import PDFExporter

        # Simulated marimo logger output with problematic \x1b(B sequence
        raw_log = (
            "\x1b[34m[D 260124 22:51:42 cell_runner:711]\x1b(B\x1b[m Running\n"
        )

        # Verify raw log causes PDF export to crash
        notebook = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("print('test')")
        cell.outputs = [
            nbformat.v4.new_output("stream", name="stderr", text=raw_log)
        ]
        notebook.cells.append(cell)

        exporter = PDFExporter()

        with pytest.raises(OSError) as e:
            exporter.from_notebook_node(notebook)

        # Clean the output (this is what from_ir.py does)
        cleaned_output = _clean_ansi_for_export(raw_log)

        # Create a notebook with stream output containing cleaned ANSI
        notebook = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("print('test')")
        cell.outputs = [
            nbformat.v4.new_output(
                "stream", name="stderr", text=cleaned_output
            )
        ]
        notebook.cells.append(cell)

        # This should not raise an error about invalid characters
        pdf_output, _resources = exporter.from_notebook_node(notebook)

        assert isinstance(pdf_output, bytes)
        assert len(pdf_output) > 0


class TestConvertMarimoTexToLatex:
    """Test conversion of marimo-tex HTML elements to standard LaTeX.

    These tests use the actual _md() function which causes LaTeX to be converted to marimo-tex HTML elements.
    """

    @pytest.mark.parametrize(
        ("latex_input", "expected_output"),
        [
            # Inline math
            (r"$f(x) = e^x$", "$f(x) = e^x$"),
            (r"$x^2 + y^2$", "$x^2 + y^2$"),
            # Block math
            (r"$$f(x) = e^x$$", "$$f(x) = e^x$$"),
            # Fractions
            (r"$\frac{x^2}{2!}$", r"$\frac{x^2}{2!}$"),
            # Greek letters
            (r"$\alpha + \beta = \gamma$", r"$\alpha + \beta = \gamma$"),
            # Square root
            (r"$\sqrt{x}$", r"$\sqrt{x}$"),
            # Subscript and superscript
            (r"$x_i^2$", r"$x_i^2$"),
            # Summation
            (r"$\sum_{i=1}^{n} x_i$", r"$\sum_{i=1}^{n} x_i$"),
            # Integral
            (r"$\int_0^1 x dx$", r"$\int_0^1 x dx$"),
            # Limits
            (
                r"$\lim_{x \to 0} \frac{\sin x}{x}$",
                r"$\lim_{x \to 0} \frac{\sin x}{x}$",
            ),
        ],
        ids=[
            "inline_exponential",
            "inline_polynomial",
            "block_exponential",
            "fractions",
            "greek_letters",
            "square_root",
            "subscript_superscript",
            "summation",
            "integral",
            "limits",
        ],
    )
    def test_simple_latex_conversion(
        self, latex_input: str, expected_output: str
    ) -> None:
        """Test simple LaTeX expressions are converted correctly."""
        html = _md(latex_input).text
        result = _convert_marimo_tex_to_latex(html)
        assert expected_output in result
        assert "marimo-tex" not in result

    def test_block_math_multiline(self) -> None:
        """Test multiline block math conversion."""
        html = _md(
            r"""$$
f(x) = 1 + x
$$"""
        ).text
        result = _convert_marimo_tex_to_latex(html)
        assert "$$" in result
        assert "f(x) = 1 + x" in result
        assert "marimo-tex" not in result

    def test_mixed_content(self) -> None:
        """Test text with embedded inline math."""
        html = _md(r"The equation $E = mc^2$ is famous.").text
        result = _convert_marimo_tex_to_latex(html)
        assert "$E = mc^2$" in result
        assert "The equation" in result
        assert "is famous" in result
        assert "marimo-tex" not in result

    def test_multiple_inline_math(self) -> None:
        """Test multiple inline math expressions."""
        html = _md(r"$a$ and $b$ and $c$").text
        result = _convert_marimo_tex_to_latex(html)
        assert "$a$" in result
        assert "$b$" in result
        assert "$c$" in result
        assert "marimo-tex" not in result

    def test_complex_document(self) -> None:
        """Test conversion of a complex document with multiple math types."""
        html = _md(
            r"""The exponential function $f(x) = e^x$ can be represented as

$$
f(x) = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \ldots
$$"""
        ).text
        result = _convert_marimo_tex_to_latex(html)
        assert "$f(x) = e^x$" in result
        assert "$$" in result
        assert r"\frac{x^2}{2!}" in result
        assert "marimo-tex" not in result

    def test_no_math_passes_through(self) -> None:
        """Test that text without math passes through unchanged."""
        html = _md("Just plain text here.").text
        result = _convert_marimo_tex_to_latex(html)
        assert "Just plain text here" in result

    def test_align_environment(self) -> None:
        """Test LaTeX align environment."""
        html = _md(
            r"""$$
\begin{align}
a &= b \\
c &= d
\end{align}
$$"""
        ).text
        result = _convert_marimo_tex_to_latex(html)
        assert "$$" in result
        assert r"\begin{align}" in result
        assert "marimo-tex" not in result

    def test_nested_md_with_inline_math(self) -> None:
        """Test nested mo.md() calls with inline math."""

        inner = _md(r"$x^2$")
        outer_html = _md(f"The value is {inner}").text

        result = _convert_marimo_tex_to_latex(outer_html)

        assert "$x^2$" in result
        assert "marimo-tex" not in result
        assert "||(" not in result

    def test_nested_md_with_block_math(self) -> None:
        """Test nested mo.md() calls with block math."""

        inner = _md(r"$$y^2$$")
        outer_html = _md(f"Result: {inner}").text

        result = _convert_marimo_tex_to_latex(outer_html)

        assert "y^2" in result
        assert "marimo-tex" not in result
        assert "||(" not in result
        assert "||[" not in result

    def test_fstring_md_with_variable(self) -> None:
        """Test mo.md() with f-string variable interpolation."""

        var = 42
        html = _md(f"Value is {var} and $x^2$").text

        result = _convert_marimo_tex_to_latex(html)

        assert "42" in result
        assert "$x^2$" in result
        assert "marimo-tex" not in result

    def test_complex_nested_md(self) -> None:
        """Test complex nested mo.md() with mixed content."""

        math_part = _md(r"$\frac{a}{b}$")
        text_with_math = _md(f"Equation: {math_part} is important").text

        result = _convert_marimo_tex_to_latex(text_with_math)

        assert r"\frac{a}{b}" in result
        assert "marimo-tex" not in result


class TestConvertLatexDelimitersForJupyter:
    """Test conversion of LaTeX delimiters for Jupyter compatibility."""

    @pytest.mark.parametrize(
        ("markdown_input", "expected"),
        [
            # Display math: \[...\] → $$...$$
            (
                r"Display math: \[f(x) = e^x\]",
                "Display math: $$f(x) = e^x$$",
            ),
            # Display math with whitespace - gets stripped
            (
                r"\[ f(x) = e^x \]",
                "$$f(x) = e^x$$",
            ),
            # Multiline display math
            (
                r"""\[
    f(x) = 1 + x + \frac{x^2}{2!}
\]""",
                r"$$f(x) = 1 + x + \frac{x^2}{2!}$$",
            ),
            # Inline math: \(...\) → $...$
            (
                r"Inline math: \(f(x) = e^x\)",
                "Inline math: $f(x) = e^x$",
            ),
            # Inline math with whitespace - gets stripped
            (
                r"\( f(x) \)",
                "$f(x)$",
            ),
            # Mixed delimiters
            (
                r"Inline \(x^2\) and display \[y^2\]",
                "Inline $x^2$ and display $$y^2$$",
            ),
            # Already using $...$ passes through unchanged
            (
                "Already $x^2$ and $$y^2$$ work",
                "Already $x^2$ and $$y^2$$ work",
            ),
            # No LaTeX at all
            (
                "Plain text without math",
                "Plain text without math",
            ),
            # Complex expression
            (
                r"\(\sigma\sqrt{100}\)",
                r"$\sigma\sqrt{100}$",
            ),
            # Multiple inline
            (
                r"\(a\) and \(b\) and \(c\)",
                "$a$ and $b$ and $c$",
            ),
        ],
        ids=[
            "display_simple",
            "display_with_spaces",
            "display_multiline",
            "inline_simple",
            "inline_with_spaces",
            "mixed_delimiters",
            "already_dollar_signs",
            "no_latex",
            "complex_expression",
            "multiple_inline",
        ],
    )
    def test_convert_latex_delimiters(
        self, markdown_input: str, expected: str
    ) -> None:
        """Test LaTeX delimiter conversion."""
        result = _convert_latex_delimiters_for_jupyter(markdown_input)
        assert result == expected

    def test_convert_latex_in_code_blocks_limitation(self) -> None:
        r"""Test that documents a known limitation with code blocks.

        Note: The simple regex approach will convert \[...\] even inside
        code blocks. This is acceptable because:
        1. Code blocks in markdown cells are rare
        2. Having \[ and \] on different lines in code is also rare
        3. A proper fix would require a full markdown parser
        """
        # This test verifies the conversion works for standalone math
        markdown = r"""Some text

\[x^2\]

More text"""

        result = _convert_latex_delimiters_for_jupyter(markdown)
        assert "$$x^2$$" in result
        assert r"\[" not in result

    def test_convert_latex_real_world_example(self) -> None:
        """Test a real-world markdown example."""
        markdown = r"""## Markdown / LaTeX

**bold** and _italic_

$\sigma\sqrt{100}$

$$
\sigma\sqrt{100}
$$

\[ \sigma\sqrt{100} \]

\( \sigma\sqrt{100} \)
"""
        expected = r"""## Markdown / LaTeX

**bold** and _italic_

$\sigma\sqrt{100}$

$$
\sigma\sqrt{100}
$$

$$\sigma\sqrt{100}$$

$\sigma\sqrt{100}$
"""
        result = _convert_latex_delimiters_for_jupyter(markdown)
        assert result == expected
