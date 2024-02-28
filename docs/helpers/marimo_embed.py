from docutils.parsers.rst import Directive
from docutils import nodes
import urllib.parse


def uri_encode(code: str) -> str:
    return urllib.parse.quote(code)


class MarimoEmbed(Directive):
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = True

    def run(self):
        header = "\n".join(
            [
                "import marimo",
                "app = marimo.App()",
                "@app.cell",
                "def __():",
                "    import marimo as mo",
                "    return",
                "",
            ]
        )
        body = header + "\n".join(self.content)
        # default, medium, large
        size = self.options.get("size", "default")
        # read, edit
        mode = self.options.get("mode", "read")
        encoded_code = uri_encode(body)

        # Create an iframe of the app
        html = f"""
        <iframe
            class="demo {size}"
            src="https://marimo.app/?code={encoded_code}&embed=true&mode={mode}"
            width="100%"
            frameBorder="0"
        ></iframe>
        """
        return [nodes.raw("", html, format="html")]
