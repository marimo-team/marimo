import marimo

__generated_with = "0.23.2"
app = marimo.App(
    width="medium",
    layout_file="layouts/kitchen_sink.slides.json",
)


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # H1 Heading
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # H1 Heading
    ## H2 Subheading
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # H1 Heading

    This is a paragraph of prose beneath the H1 heading to see how body text sits under the title.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## H2 Heading
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## H2 Heading

    A paragraph beneath the H2 heading.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## H2 Heading

    - First bullet point
    - Second bullet point
    - Third bullet point
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Hi
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Hi
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("# " + "A really long H1 heading that keeps on going and going " * 6)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("## " + "A really long H2 heading that keeps on going and going " * 7)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("# Centered H1").center()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # H1 Heading
    ## H2 Subheading
    """).center()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # H1 Heading
    ## H2 Subheadings
    """).left()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.stat(
        value="1,234",
        label="Active users",
        caption="+12% vs last week",
        direction="increase",
    )
    return


@app.cell(hide_code=True)
def _():
    import altair as _alt
    import pandas as _pd

    _chart_df = _pd.DataFrame(
        {"x": list(range(20)), "y": [i * i for i in range(20)]}
    )
    _alt.Chart(_chart_df).mark_line(point=True).encode(x="x", y="y").properties(
        width=400, height=300
    )
    return


@app.cell(hide_code=True)
def _(mo):
    import pandas as _pd

    _df = _pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Carol", "Dave", "Eve"],
            "score": [92, 88, 77, 95, 81],
            "team": ["A", "B", "A", "C", "B"],
        }
    )
    mo.ui.table(_df)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "First section": mo.md("Content of the first section."),
            "Second section": mo.md("Content of the second section."),
            "Third section": mo.md("Content of the third section."),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.ui.tabs(
        {
            "Overview": mo.md("This is the overview tab."),
            "Details": mo.md("This is the details tab."),
            "Settings": mo.md("This is the settings tab."),
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.hstack([mo.md("Left"), mo.md("Middle"), mo.md("Right")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([mo.md("Top"), mo.md("Middle"), mo.md("Bottom")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.hstack([mo.md("Left"), mo.md("Middle"), mo.md("Right")], widths="equal")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([mo.md("Top"), mo.md("Middle"), mo.md("Bottom")], heights="equal")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack(
        [
            mo.hstack([mo.md("A"), mo.md("B"), mo.md("C")], widths="equal"),
            mo.hstack([mo.md("D"), mo.md("E"), mo.md("F")], widths="equal"),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.Html(
        "<div style='white-space: nowrap;'>"
        + "this is a very long horizontal line that will overflow &nbsp; " * 40
        + "</div>"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("\n\n".join([f"Line {i + 1}" for i in range(200)]))
    return


@app.cell(hide_code=True)
def _(mo):
    import pandas as _pd

    mo.ui.table(_pd.DataFrame({"value": [42]}))
    return


@app.cell(hide_code=True)
def _(mo):
    import pandas as _pd

    _big = _pd.DataFrame({f"col_{c:02d}": list(range(100)) for c in range(100)})
    mo.ui.table(_big)
    return


@app.cell
def _(mo):
    mo.Html('<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.image("https://picsum.photos/seed/marimo/400/300")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.hstack(["text", mo.image("https://picsum.photos/seed/hs/200/150")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack(["text", mo.image("https://picsum.photos/seed/vs/200/150")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack(["# text", mo.image("https://picsum.photos/seed/vs1/200/150")])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack(["## text", mo.image("https://picsum.photos/seed/vs2/200/150")])
    return


@app.cell(hide_code=True)
def _():
    import anywidget as _anywidget
    import traitlets as _traitlets


    class _CounterWidget(_anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            const btn = document.createElement("button");
            btn.style.padding = "0.5rem 1rem";
            const paint = () => { btn.innerHTML = `clicked ${model.get("value")} times`; };
            paint();
            btn.addEventListener("click", () => {
                model.set("value", model.get("value") + 1);
                model.save_changes();
            });
            model.on("change:value", paint);
            el.appendChild(btn);
        }
        export default { render };
        """
        value = _traitlets.Int(0).tag(sync=True)


    _CounterWidget()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.iframe("https://marimo.io/")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.Html(
        "<div style='padding: 1rem; border: 2px solid #8b5cf6; border-radius: 8px; background: #f5f3ff;'>Custom HTML content via <code>mo.Html</code></div>"
    )
    return


if __name__ == "__main__":
    app.run()
