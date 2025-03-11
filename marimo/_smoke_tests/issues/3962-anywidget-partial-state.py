import marimo

__generated_with = "0.11.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import anywidget
    import traitlets
    import marimo as mo
    from svg import SVG, Circle
    return Circle, SVG, anywidget, mo, traitlets


@app.cell
def _(anywidget, traitlets):
    class HoverWidget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            el.innerHTML = model.get("svg");
            el.querySelectorAll("circle").forEach((circle) => {
                circle.addEventListener("mouseover", () => {
                    model.set("selected_id", circle.getAttribute("id"));
                    model.save_changes();
                });
            });
        }
        export default { render };
        """
        svg = traitlets.Unicode().tag(sync=True)
        selected_id = traitlets.Any().tag(sync=True)
    return (HoverWidget,)


@app.cell
def _(Circle, SVG):
    my_svg = SVG(
        width=200,
        height=100,
        elements=[
            Circle(id="circle 1", cx=50, cy=50, r=20, fill="red"),
            Circle(id="circle 2", cx=100, cy=50, r=20, fill="blue"),
            Circle(id="circle 3", cx=150, cy=50, r=20, fill="green"),
        ],
    )
    return (my_svg,)


@app.cell
def _(HoverWidget, mo, my_svg):
    w = mo.ui.anywidget(HoverWidget(svg=my_svg.as_str(), selected_id=""))
    [w]
    return (w,)


if __name__ == "__main__":
    app.run()
