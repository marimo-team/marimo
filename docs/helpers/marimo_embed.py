import urllib.parse


def uri_encode_component(code: str) -> str:
    return urllib.parse.quote(code, safe="~()*!.'")


def create_marimo_iframe(
    code: str,
    size: str = "default",
    mode: str = "read",
    app_width: str = "normal",
) -> str:
    header = "\n".join(
        [
            "import marimo",
            f'app = marimo.App(width="{app_width}")',
            "",
        ]
    )
    footer = "\n".join(
        [
            "",
            "@app.cell",
            "def __():",
            "    import marimo as mo",
            "    return",
        ]
    )
    body = header + code + footer
    encoded_code = uri_encode_component(body)

    return f"""<iframe
    class="demo {size}"
    src="https://marimo.app/?code={encoded_code}&embed=true&mode={mode}"
    allow="camera; geolocation; microphone; fullscreen; autoplay; encrypted-media; picture-in-picture; clipboard-read; clipboard-write"
    width="100%"
    frameBorder="0"
></iframe>"""
