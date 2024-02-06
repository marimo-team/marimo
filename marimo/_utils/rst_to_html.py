from docutils.core import publish_parts


def convert_rst_to_html(rst_content: str) -> str:
    """Convert RST content to HTML."""

    return publish_parts(
        rst_content,
        writer_name="html",
        settings_overrides={
            # "output_encoding": "unicode",
            # "initial_header_level": 2,
            # "syntax_highlight": "short",
            # "stylesheet_path": None,
            # "math_output": "MathJax",
            # "math_output_options": {"mathjax": "SVG"},
            # "field_name_limit": 0,
            # "strip_elements_with_classes": ["toctree-wrapper"],
        },
    )["html_body"]
