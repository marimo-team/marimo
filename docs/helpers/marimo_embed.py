from docutils.parsers.rst import Directive
from docutils import nodes
import urllib.parse


def uri_encode_component(code: str) -> str:
    return urllib.parse.quote(code, safe="~()*!.'")


class MarimoEmbed(Directive):
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = True
    option_spec = {
        # default, medium, large
        "size": str,
        # read, edit
        "mode": str,
        # normal, full
        "app_width": str,
    }

    def run(self):
        # Configs
        size = self.options.get("size", "default")
        mode = self.options.get("mode", "read")
        app_width = self.options.get("app_width", "normal")

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
        body = header + "\n".join(self.content) + footer
        encoded_code = uri_encode_component(body)

        # Create an iframe of the app
        html = f"""
        <iframe
            class="demo {size}"
            src="https://marimo.app/?code={encoded_code}&embed=true&mode={mode}"
            allow="camera; geolocation; microphone; fullscreen; autoplay; encrypted-media; picture-in-picture; clipboard-read; clipboard-write"
            width="100%"
            frameBorder="0"
        ></iframe>
        """
        return [nodes.raw("", html, format="html")]
