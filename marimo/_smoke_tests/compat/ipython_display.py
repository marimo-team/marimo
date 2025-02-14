# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ipython==8.31.0",
#     "marimo",
#     "numpy==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.11.4"
app = marimo.App(width="medium")


@app.cell
def _():
    from IPython.display import (
        Audio,
        display,
        HTML,
        Image,
        JSON,
        Javascript,
        Latex,
        Markdown,
        Math,
        # PDF,
        Pretty,
        SVG,
        Video,
        YouTubeVideo,
        Code,
        IFrame,
    )
    return (
        Audio,
        Code,
        HTML,
        IFrame,
        Image,
        JSON,
        Javascript,
        Latex,
        Markdown,
        Math,
        Pretty,
        SVG,
        Video,
        YouTubeVideo,
        display,
    )


@app.cell
def _(HTML):
    html = HTML("<h1>Hello World</h1><p style='color: blue;'>This is HTML</p>")
    html
    return (html,)


@app.cell
def _(Image):
    # Using a sample image URL
    image = Image(url="https://marimo.io/logo.png", width=100)
    image
    return (image,)


@app.cell
def _(JSON):
    json_data = JSON(
        {
            "name": "marimo",
            "type": "notebook",
            "features": ["interactive", "reactive"],
        }
    )
    json_data
    return (json_data,)


@app.cell
def _(Javascript):
    # Not yet supported
    js = Javascript("alert('Hello from JavaScript!');")
    js
    return (js,)


@app.cell
def _(Latex):
    latex = Latex(r"\begin{align}f(x) &= x^2\\g(x) &= \frac{1}{x}\end{align}")
    latex
    return (latex,)


@app.cell
def _(Math):
    math = Math(
        r"\frac{1}{\pi} = \frac{2\sqrt{2}}{9801} \sum_{k=0}^\infty \frac{(4k)!(1103+26390k)}{(k!)^4 396^{4k}}"
    )
    math
    return (math,)


@app.cell
def _(Pretty):
    _data = '{"complex": [1, 2, {"nested": "structure"}]}'
    pretty = Pretty(_data)
    pretty
    return (pretty,)


@app.cell
def _(SVG):
    svg = SVG(
        '<svg height="100" width="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>'
    )
    svg
    return (svg,)


@app.cell
def _(Audio):
    # Example with synthesized audio data
    import numpy as np

    sample_rate = 44100
    t = np.linspace(0, 2, 2 * sample_rate)
    data = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
    audio = Audio(data=data, rate=sample_rate)
    audio
    return audio, data, np, sample_rate, t


@app.cell
def _(Video):
    # Using a sample video URL
    video = Video("https://www.w3schools.com/html/mov_bbb.mp4")
    video
    return (video,)


@app.cell
def _(YouTubeVideo):
    # Example YouTube video
    yt = YouTubeVideo("dQw4w9WgXcQ")
    yt
    return (yt,)


@app.cell
def _(Code):
    code = Code(
        """def hello_world():
    print("Hello, World!")""",
        language="python",
    )
    code
    return (code,)


@app.cell
def _(IFrame):
    iframe = IFrame("https://marimo.io", width=800, height=450)
    iframe
    return (iframe,)


@app.cell
def _(Markdown):
    markdown = Markdown(
        """
    ## This is a Markdown Example
    Here is a list:
    - Item 1
    - Item 2
    - Item 3

    And some **bold** and *italic* text.
        """
    )
    markdown
    return (markdown,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Display Commands""")
    return


@app.cell
def _(Markdown, display):
    display(Markdown("**hello**"))
    display(Markdown("_goodbye*"))
    return


@app.cell
def _():
    from IPython.display import (
        display_pretty,
        display_html,
        display_markdown,
        display_svg,
        display_png,
        display_jpeg,
        display_latex,
        display_json,
        display_javascript,
        display_pdf,
    )
    return (
        display_html,
        display_javascript,
        display_jpeg,
        display_json,
        display_latex,
        display_markdown,
        display_pdf,
        display_png,
        display_pretty,
        display_svg,
    )


@app.cell
def _(
    display_html,
    display_jpeg,
    display_png,
    display_pretty,
    display_svg,
):
    # Working
    display_pretty("hello", raw=True)
    display_html("<h1 style='color: blue'>Hello World</h1>", raw=True)
    display_svg(
        '<svg height="100" width="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>',
        raw=True,
    )
    display_png("https://marimo.io/favicon.ico", raw=True)
    display_jpeg("https://marimo.io/favicon.ico", raw=True)
    return


@app.cell
def _(
    display_javascript,
    display_json,
    display_latex,
    display_markdown,
    display_pdf,
):
    # Broken or not yet supported
    display_markdown("## Hello World", raw=True)
    display_latex(
        r"\begin{align}f(x) &= x^2\\g(x) &= \frac{1}{x}\end{align}", raw=True
    )
    display_json(
        {
            "name": "marimo",
            "type": "notebook",
            "features": ["interactive", "reactive"],
        },
        raw=True,
    )
    display_javascript("alert('Hello from JavaScript!');", raw=True)
    display_pdf("https://marimo.io/logo.png", raw=True)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
