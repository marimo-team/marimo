from __future__ import annotations

import html
from typing import Any
from unittest.mock import Mock, patch

from marimo._output.formatters.utils import src_or_src_doc
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_srcdoc_in_notebook() -> None:
    html_content = "<html><body>Hello, World!</body></html>"
    escaped_html_content = html.escape(html_content)

    result = src_or_src_doc(html_content)
    assert result == {"srcdoc": escaped_html_content}


@patch(
    "marimo._output.formatters.utils.mo_data.html",
    return_value=Mock(url="file_url"),
)
def test_src_in_notebook(
    mock_html: Any, executing_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    del executing_kernel
    del exec_req
    html_content = "<html><body>Hello, World!</body></html>"
    result = src_or_src_doc(html_content)
    assert result == {"src": "file_url"}
    mock_html.assert_called_once_with(html_content)
