# Copyright 2024 Marimo. All rights reserved.
from docutils.core import publish_parts


def convert_rst_to_html(rst_content: str) -> str:
    """Convert RST content to HTML."""

    return publish_parts(
        rst_content,
        writer_name="html",
        settings_overrides={
            "warning_stream": None,
            "file_insertion_enabled": False,
            "report_level": 5,
        },
    )["html_body"]
