from __future__ import annotations

import base64
import html
from typing import Any

import marimo as mo
from marimo._output import formatting
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.md import md


class SagemathFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "sage"

    def register(self) -> None:
        from sage.repl.rich_output import get_display_manager  # type: ignore
        from sage.repl.rich_output.backend_base import (
            BackendBase,  # type: ignore
        )
        from sage.repl.rich_output.output_basic import (
            OutputBase,  # type: ignore
        )
        from sage.repl.rich_output.output_catalog import (  # type: ignore
            OutputAsciiArt,
            OutputHtml,
            OutputImagePng,
            OutputImageSvg,
            OutputLatex,
            OutputPlainText,
            OutputSceneThreejs,
            OutputUnicodeArt,
        )
        from sage.structure.sage_object import SageObject  # type: ignore

        def _render_rich_output(
            rich_output: Any, fallback_obj: Any = None
        ) -> tuple[str, str]:
            if isinstance(rich_output, OutputSceneThreejs):
                escaped_html = html.escape(rich_output.html.get_str())

                # custom width and height to allow the user to resize the iframe
                width = getattr(fallback_obj, "marimo_width", "100%")
                height = getattr(fallback_obj, "marimo_height", "500px")

                iframe = f"""
                <iframe srcdoc="{escaped_html}"
                        width="{width}"
                        height="{height}"
                        style="border: 0;">
                </iframe>
                """
                return ("text/html", iframe)

            elif isinstance(rich_output, OutputImagePng):
                b64 = base64.b64encode(rich_output.png.get()).decode("ascii")
                return (
                    "text/html",
                    f'<img src="data:image/png;base64,{b64}" />',
                )

            elif isinstance(rich_output, OutputImageSvg):
                return ("text/html", rich_output.svg.get_str())

            elif isinstance(rich_output, OutputHtml):
                html_str = rich_output.html.get_str()
                # the default sage latex formatter outputs latex with <html> tags
                # we strip them if present
                if html_str.startswith("<html>") and html_str.endswith(
                    "</html>"
                ):
                    html_str = html_str[len("<html>") : -len("</html>")]
                return (
                    "text/html",
                    md(f"""{html_str}""").text,
                )

            # since we have OutputHtml enabled, the sage output formatter automatically
            # outputs rich output as MathJax HTML. This one is for raw latex output
            elif isinstance(rich_output, OutputLatex):
                return (
                    "text/html",
                    md(f"""\\[{rich_output.latex.get_str()}\\]""").text,
                )

            elif isinstance(rich_output, OutputAsciiArt):
                return (
                    "text/html",
                    f"<pre>{html.escape(rich_output.ascii_art.get_str())}</pre>",
                )

            elif isinstance(rich_output, OutputUnicodeArt):
                return (
                    "text/html",
                    f"<pre>{html.escape(rich_output.unicode_art.get_str())}</pre>",
                )

            elif isinstance(rich_output, OutputPlainText):
                return ("text/plain", rich_output.text.get_str())

            # Fallback
            if fallback_obj is not None:
                try:
                    return (
                        "text/html",
                        md(f"""\\[{fallback_obj._latex_()}\\]""").text,
                    )
                except (AttributeError, TypeError):
                    return ("text/plain", repr(fallback_obj))

            return ("text/plain", repr(rich_output))

        class BackendMarimo(BackendBase):
            def _repr_(self) -> str:
                return "Marimo Notebook"

            def supported_output(self) -> set:
                return {
                    OutputPlainText,
                    OutputAsciiArt,
                    OutputUnicodeArt,
                    OutputHtml,
                    OutputImagePng,
                    OutputImageSvg,
                    OutputSceneThreejs,
                    OutputLatex,
                }

            def threejs_offline_scripts(self) -> str:
                return get_display_manager().threejs_scripts(online=True)

            def display_immediately(
                self, plain_text: Any, rich_output: Any
            ) -> None:
                mo.output.append(rich_output)

        # add our marimo backend to sage's display manager
        dm = get_display_manager()

        if type(dm._backend).__name__ != "BackendMarimo":
            dm.switch_backend(BackendMarimo())

            # latex output by default
            dm.preferences.text = "latex"

        @formatting.formatter(SageObject)
        def _show_sage_object(sobj: SageObject) -> tuple[str, str]:
            plain_text, rich_output = dm._rich_output_formatter(sobj, dict())
            return _render_rich_output(rich_output, fallback_obj=sobj)

        def _show_output_base(obj: Any) -> tuple[str, str]:
            return _render_rich_output(obj)

        output_classes = [
            OutputPlainText,
            OutputAsciiArt,
            OutputUnicodeArt,
            OutputHtml,
            OutputImagePng,
            OutputImageSvg,
            OutputSceneThreejs,
            OutputLatex,
        ]

        for cls in output_classes:
            formatting.formatter(cls)(_show_output_base)
