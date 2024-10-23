# Copyright 2024 Marimo. All rights reserved.
import contextlib
import io


def convert_rst_to_html(rst_content: str) -> str:
    """Convert RST content to HTML."""

    from docutils.core import publish_parts  # type: ignore[import-untyped]

    # redirect stderr and ignore it to silence error messages
    with contextlib.redirect_stderr(io.StringIO()) as _:
        parts = publish_parts(
            rst_content,
            writer_name="html",
            settings_overrides={
                "warning_stream": None,
                "file_insertion_enabled": False,
                "report_level": 5,
            },
        )
    return parts["html_body"]  # type: ignore[no-any-return]
