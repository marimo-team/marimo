# Copyright 2026 Marimo. All rights reserved.
"""Export marimo notebooks to Jupyter ipynb format."""

from __future__ import annotations

import io
import json
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from marimo._ast.cell import Cell, CellConfig
from marimo._ast.errors import CycleError, MultipleDefinitionError
from marimo._ast.names import is_internal_cell_name
from marimo._convert.common.format import get_markdown_from_cell
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    Error as MarimoError,
    MarimoExceptionRaisedError,
)
from marimo._messaging.mimetypes import METADATA_KEY
from marimo._runtime import dataflow

if TYPE_CHECKING:
    from nbformat.notebooknode import NotebookNode  # type: ignore

    from marimo._ast.app import InternalApp
    from marimo._session.state.session_view import SessionView


# Note: We intentionally omit "version" as it would vary across environments
# and break reproducibility. The marimo_version in metadata is sufficient.
DEFAULT_LANGUAGE_INFO = {
    "codemirror_mode": {"name": "ipython", "version": 3},
    "file_extension": ".py",
    "mimetype": "text/x-python",
    "name": "python",
    "nbconvert_exporter": "python",
    "pygments_lexer": "ipython3",
}


def convert_from_ir_to_ipynb(
    app: InternalApp,
    *,
    sort_mode: Literal["top-down", "topological"],
    session_view: Optional[SessionView] = None,
) -> str:
    """Export notebook as .ipynb, optionally including outputs.

    Args:
        app: The internal app to export
        sort_mode: How to order cells - "top-down" preserves notebook order,
                   "topological" orders by dependencies
        session_view: Optional session view to include cell outputs

    Returns:
        JSON string of the .ipynb notebook
    """

    DependencyManager.nbformat.require("to convert marimo notebooks to ipynb")
    import nbformat  # type: ignore[import-not-found]

    from marimo import __version__

    notebook = nbformat.v4.new_notebook()  # type: ignore[no-untyped-call]
    notebook["cells"] = []

    # Add marimo-specific notebook metadata
    marimo_metadata: dict[str, Any] = {
        "marimo_version": __version__,
    }
    app_config_diff = app.config.asdict_difference()
    if app_config_diff:
        marimo_metadata["app_config"] = app_config_diff
    # Include header if present (PEP 723 metadata, docstrings, etc.)
    if app._app._header:
        marimo_metadata["header"] = app._app._header
    notebook["metadata"]["marimo"] = marimo_metadata

    # Add standard Jupyter language_info (no kernelspec)
    notebook["metadata"]["language_info"] = DEFAULT_LANGUAGE_INFO

    # Determine cell order based on sort_mode
    if sort_mode == "top-down":
        cell_data_list = list(app.cell_manager.cell_data())
    else:
        # Topological sort - try to sort, fall back to top-down on cycle
        try:
            graph = app.graph
            sorted_ids = dataflow.topological_sort(graph, graph.cells.keys())
            # Build cell_data list in topological order
            cell_data_list = [
                app.cell_manager.cell_data_at(cid)
                for cid in sorted_ids
                if cid in graph.cells
            ]
        except (CycleError, MultipleDefinitionError):
            # Fall back to top-down order if graph is invalid
            cell_data_list = list(app.cell_manager.cell_data())

    for cell_data in cell_data_list:
        cid = cell_data.cell_id

        # Get outputs if session_view is provided
        outputs: list[NotebookNode] = []
        if session_view is not None:
            cell_output = session_view.get_cell_outputs([cid]).get(cid, None)
            cell_console_outputs = session_view.get_cell_console_outputs(
                [cid]
            ).get(cid, [])
            outputs = _convert_marimo_output_to_ipynb(
                cell_output, cell_console_outputs
            )

        notebook_cell = _create_ipynb_cell(
            cell_id=cid,
            code=cell_data.code,
            name=cell_data.name,
            config=cell_data.config,
            cell=cell_data.cell,
            outputs=outputs,
        )
        notebook["cells"].append(notebook_cell)

    stream = io.StringIO()
    nbformat.write(notebook, stream)  # type: ignore[no-untyped-call]
    stream.seek(0)
    return stream.read()


def _create_ipynb_cell(
    cell_id: str,
    code: str,
    name: str,
    config: CellConfig,
    cell: Optional[Cell],
    outputs: list[NotebookNode],
) -> NotebookNode:
    """Create an ipynb cell with metadata.

    Args:
        cell_id: The cell's unique identifier
        code: The cell's source code
        name: The cell's name
        config: The cell's configuration
        cell: Optional Cell object for markdown detection
        outputs: List of cell outputs (ignored for markdown cells)
    """
    import nbformat

    # Try to extract markdown if we have a valid Cell
    if cell is not None:
        markdown_string = get_markdown_from_cell(cell, code)
        if markdown_string is not None:
            # Note: This handles modern LaTeX syntax like \[...\]
            # However they are not supported by Jupyter https://github.com/jupyter/nbconvert/issues/477
            # Hence, leaving out for now.
            # markdown_string = _convert_latex_delimiters_for_jupyter(
            #     markdown_string
            # )
            node = cast(
                nbformat.NotebookNode,
                nbformat.v4.new_markdown_cell(markdown_string, id=cell_id),  # type: ignore[no-untyped-call]
            )
            _add_marimo_metadata(node, name, config)
            return node

    node = cast(
        nbformat.NotebookNode,
        nbformat.v4.new_code_cell(code, id=cell_id),  # type: ignore[no-untyped-call]
    )
    if outputs:
        node.outputs = outputs
    _add_marimo_metadata(node, name, config)
    return node


def _add_marimo_metadata(
    node: NotebookNode, name: str, config: CellConfig
) -> None:
    """Add marimo-specific metadata to a notebook cell."""
    marimo_metadata: dict[str, Any] = {}
    if config.is_different_from_default():
        marimo_metadata["config"] = config.asdict_without_defaults()
    if not is_internal_cell_name(name):
        marimo_metadata["name"] = name
    if marimo_metadata:
        node["metadata"]["marimo"] = marimo_metadata


# Output conversion helpers


def _maybe_extract_dataurl(data: Any) -> Any:
    if (
        isinstance(data, str)
        and data.startswith("data:")
        and ";base64," in data
    ):
        return data.split(";base64,")[1]
    else:
        return data


def _is_marimo_component(html_content: Any) -> bool:
    """Check if the content is a marimo component."""
    if isinstance(html_content, list):
        html_content = "".join(html_content)
    if not isinstance(html_content, str):
        return False
    return "<marimo-" in html_content


class _HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)

    def get_text(self) -> str:
        return "".join(self.text_parts)


def _strip_html_from_traceback(html_traceback: str) -> list[str]:
    """Convert HTML-formatted traceback to plain text lines.

    Also strips temporary file paths from tracebacks. Exports run cells in
    the kernel which compiles them with temp file paths. It's not easy to
    set anonymous source since exports are done in the kernel, so we strip
    the paths here instead.
    """
    parser = _HTMLTextExtractor()
    parser.feed(html_traceback)
    text = parser.get_text()

    # Strip temp file paths like /tmp/marimo_12345/__marimo__cell_Hbol_.py
    # Replace with empty string to get cleaner tracebacks
    text = re.sub(r'[^"]*__marimo__cell_[^"]*\.py', "", text)

    return text.splitlines()


def _extract_traceback_from_console(
    console_outputs: list[CellOutput],
) -> list[str]:
    """Extract traceback lines from console outputs."""
    for output in console_outputs:
        if (
            output.channel == CellChannel.STDERR
            and output.mimetype == "application/vnd.marimo+traceback"
        ):
            return _strip_html_from_traceback(str(output.data))
    return []


def _get_error_info(
    error: Union[MarimoError, dict[str, Any]],
) -> tuple[str, str]:
    """Extract ename and evalue from a marimo error."""
    from marimo._messaging.msgspec_encoder import asdict

    if isinstance(error, dict):
        return error.get("type", "UnknownError"), error.get("msg", "")
    elif isinstance(error, MarimoExceptionRaisedError):
        return error.exception_type, error.msg.rstrip().strip(":")
    else:
        # For other error types, use the tag as ename and describe() as evalue
        error_dict = asdict(error)
        return error_dict.get("type", "Error"), error.describe()


def _convert_output_to_ipynb(
    output: CellOutput,
) -> Optional[NotebookNode]:
    """Convert certain outputs (OUTPUT/MEDIA channel) to IPython notebook format.

    Outputs like rich elements and LaTeX are converted to ensure they are compatible with IPython notebook format.

    Returns None if the output should be skipped or produces no data.
    """
    import nbformat

    if output.data is None:
        return None

    if output.channel not in (CellChannel.OUTPUT, CellChannel.MEDIA):
        return None

    if output.mimetype == "text/plain" and (
        output.data == [] or output.data == ""
    ):
        return None

    data: dict[str, Any] = {}
    metadata: dict[str, Any] = {}

    if output.mimetype == "application/vnd.marimo+error":
        # Errors are handled separately via MARIMO_ERROR channel
        return None
    elif output.mimetype == "application/vnd.marimo+mimebundle":
        if isinstance(output.data, dict):
            mimebundle = output.data
        elif isinstance(output.data, str):
            mimebundle = json.loads(output.data)
        else:
            raise ValueError(f"Invalid data type: {type(output.data)}")

        for mime, content in mimebundle.items():
            if mime == METADATA_KEY and isinstance(content, dict):
                metadata = content
            elif mime == "text/html" and _is_marimo_component(content):
                # Skip marimo components because they cannot be rendered
                # in IPython notebook format
                continue
            else:
                data[mime] = _maybe_extract_dataurl(content)
    elif output.mimetype == "text/markdown" and isinstance(output.data, str):
        data[output.mimetype] = _convert_marimo_tex_to_latex(output.data)
    else:
        data[output.mimetype] = _maybe_extract_dataurl(output.data)

    if not data:
        return None

    return cast(
        nbformat.NotebookNode,
        nbformat.v4.new_output(  # type: ignore[no-untyped-call]
            "display_data",
            data=data,
            metadata=metadata,
        ),
    )


def _clean_ansi_for_export(text: Any) -> str:
    """Clean ANSI escape codes for export, keeping color codes intact.

    ANSI codes are terminal styling sequences (colors, bold, cursor movement)
    used by logging libraries like rich, colorama, and marimo's own logger.

    We keep standard color codes (like \\x1b[34m) so nbconvert's LaTeX template
    can convert them to colors via its ansi2latex filter. However, we must strip
    character set selection sequences (like \\x1b(B) which nbconvert doesn't
    handle and cause LaTeX to fail with "invalid character" errors.
    """
    if not isinstance(text, str):
        return str(text)
    # Strip character set selection sequences: ESC ( <char> or ESC ) <char>
    # These have no visual effect and cause LaTeX compilation to fail
    return re.sub(r"\x1b[()][A-Z0-9]", "", text)


def _convert_marimo_output_to_ipynb(
    cell_output: Optional[CellOutput], console_outputs: list[CellOutput]
) -> list[NotebookNode]:
    """Convert marimo output format to IPython notebook format."""
    import nbformat

    ipynb_outputs: list[NotebookNode] = []

    # Handle console outputs (stdout/stderr/media)
    for console_out in console_outputs:
        if console_out.channel == CellChannel.STDOUT:
            ipynb_outputs.append(
                cast(
                    nbformat.NotebookNode,
                    nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                        "stream",
                        name="stdout",
                        # https://nbformat.readthedocs.io/en/latest/format_description.html#stream-output
                        text=_clean_ansi_for_export(console_out.data),
                    ),
                )
            )
        elif console_out.channel == CellChannel.STDERR:
            # Skip tracebacks - they're included in error outputs
            if console_out.mimetype == "application/vnd.marimo+traceback":
                continue
            ipynb_outputs.append(
                cast(
                    nbformat.NotebookNode,
                    nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                        "stream",
                        name="stderr",
                        text=_clean_ansi_for_export(console_out.data),
                    ),
                )
            )
        elif console_out.channel in (CellChannel.OUTPUT, CellChannel.MEDIA):
            ipynb_compatible_output = _convert_output_to_ipynb(console_out)
            if ipynb_compatible_output is not None:
                ipynb_outputs.append(ipynb_compatible_output)

    if not cell_output:
        return ipynb_outputs

    if cell_output.data is None:
        return ipynb_outputs

    if cell_output.channel == CellChannel.MARIMO_ERROR:
        traceback_lines = _extract_traceback_from_console(console_outputs)
        errors = cast(
            list[Union[MarimoError, dict[str, Any]]], cell_output.data
        )
        for error in errors:
            ename, evalue = _get_error_info(error)
            ipynb_outputs.append(
                cast(
                    nbformat.NotebookNode,
                    nbformat.v4.new_output(  # type: ignore[no-untyped-call]
                        "error",
                        ename=ename,
                        evalue=evalue,
                        traceback=traceback_lines,
                    ),
                )
            )
        return ipynb_outputs

    ipynb_compatible_output = _convert_output_to_ipynb(cell_output)
    if ipynb_compatible_output is not None:
        ipynb_outputs.append(ipynb_compatible_output)

    return ipynb_outputs


def _convert_latex_delimiters_for_jupyter(markdown_string: str) -> str:
    """Convert LaTeX delimiters that nbconvert can't handle."""

    # Convert display math \[...\] to $$...$$
    # Preserve internal whitespace but trim the delimiter boundaries
    def replace_display(match: re.Match[str]) -> str:
        content = match.group(1)
        return f"$${content.strip()}$$"

    markdown_string = re.sub(
        r"\\\[(.*?)\\\]", replace_display, markdown_string, flags=re.DOTALL
    )

    # Convert inline math \(...\) to $...$
    # Remove spaces adjacent to delimiters
    def replace_inline(match: re.Match[str]) -> str:
        content = match.group(1)
        return f"${content.strip()}$"

    markdown_string = re.sub(
        r"\\\((.*?)\\\)", replace_inline, markdown_string, flags=re.DOTALL
    )

    return markdown_string


def _convert_marimo_tex_to_latex(html_string: str) -> str:
    """Convert marimo-tex elements back to standard LaTeX delimiters.
    Keep in sync with TexPlugin.tsx

    Converts:
    - <marimo-tex ...>||(content||)</marimo-tex> → $content$ (inline)
    - <marimo-tex ...>||[content||]</marimo-tex> → $$content$$ (block)
    - <marimo-tex ...>||(||(content||)||)</marimo-tex> → $$content$$ (nested display)
    """

    def replace_tex(match: re.Match[str]) -> str:
        content = match.group(1)

        # Handle nested display math: ||(||(content||)||)
        # Must check this FIRST and be more specific
        if content.startswith("||(||(") and content.endswith("||)||)"):
            inner = content[6:-6]  # Strip ||(||( and ||)||)
            return f"$${inner}$$"
        # Handle block math: ||[content||]
        elif content.startswith("||[") and content.endswith("||]"):
            inner = content[3:-3]
            return f"$${inner}$$"
        # Handle inline math: ||(content||)
        elif content.startswith("||(") and content.endswith("||)"):
            inner = content[3:-3]
            return f"${inner}$"  # Single $ for inline!
        else:
            return content

    # Match <marimo-tex ...>content</marimo-tex>
    # Use non-greedy matching and handle potential attributes
    pattern = r"<marimo-tex[^>]*>(.*?)</marimo-tex>"

    return re.sub(pattern, replace_tex, html_string, flags=re.DOTALL)
