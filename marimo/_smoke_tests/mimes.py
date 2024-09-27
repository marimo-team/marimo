# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "vegafusion",
#     "pandas",
#     "altair",
# ]
# ///

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    class HTMLMime:
        def _mime_(self):
            return (
                "text/html",
                "<h1>Hello, World!</h1>",
            )


    HTMLMime()
    return HTMLMime,


@app.cell
def __():
    class SvgMime:
        def _mime_(self):
            return (
                "image/svg+xml",
                '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>',
            )


    SvgMime()
    return SvgMime,


@app.cell
def __():
    class JSONMime:
        def _mime_(self):
            return (
                "application/json",
                '{"message": "Hello, World!"}',
            )


    JSONMime()
    return JSONMime,


@app.cell
def __():
    class PngMime:
        def _mime_(self):
            import matplotlib.pyplot as plt
            import io
            import base64

            # Create a figure
            fig, ax = plt.subplots()
            ax.plot([1, 2, 3, 4, 5], [1, 4, 9, 16, 25])

            # Save the plot to a BytesIO object
            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            plt.close(fig)
            buf.seek(0)

            # Read as bytes
            data = buf.read()
            return ("image/png", data)


    PngMime()
    return PngMime,


@app.cell
def __():
    class CSVMime:
        def _mime_(self):
            return (
                "text/csv",
                "name,age\nAlice,30\nBob,25",
            )


    CSVMime()
    return CSVMime,


@app.cell
def __():
    class TextMarkdownMime:
        def _mime_(self):
            return (
                "text/markdown",
                "# Markdown Title\n\n*This text will be italic*\n\n**This text will be bold**",
            )


    TextMarkdownMime()
    return TextMarkdownMime,


@app.cell
def __():
    import altair as alt
    import pandas as pd


    class VegaLiteMime:
        def _mime_(self):
            # Create a sample dataframe
            data = pd.DataFrame({"x": range(10), "y": [x**2 for x in range(10)]})

            # Create a chart
            chart = alt.Chart(data).mark_line().encode(x="x", y="y")

            # Return the Vega-Lite specification
            # return ("application/json", chart.to_json())
            return ("application/vnd.vegalite.v5+json", chart.to_json())


    VegaLiteMime()
    return VegaLiteMime, alt, pd


@app.cell
def __():
    class UnknownMime:
        def _mime_(self):
            return (
                "application/octet-stream",
                "This is a binary file without a specific format.",
            )


    UnknownMime()
    return UnknownMime,


@app.cell
def __(
    CSVMime,
    HTMLMime,
    JSONMime,
    SvgMime,
    TextMarkdownMime,
    UnknownMime,
    VegaLiteMime,
):
    class ReprMimeBundle:
        def __init__(self, *mimes):
            self.mimes = mimes

        def _repr_mimebundle_(self):
            bundle = {}
            for mime in self.mimes:
                mime_type, data = mime._mime_()
                bundle[mime_type] = data
            return bundle


    # Example usage with multiple MIME types
    ReprMimeBundle(
        VegaLiteMime(),
        HTMLMime(),
        SvgMime(),
        JSONMime(),
        CSVMime(),
        TextMarkdownMime(),
        UnknownMime(),
    )
    return ReprMimeBundle,


@app.cell
def __(HTMLMime, ReprMimeBundle):
    ReprMimeBundle(HTMLMime())
    return


if __name__ == "__main__":
    app.run()
