import marimo

__generated_with = "0.11.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import anywidget
    import traitlets
    return anywidget, mo, traitlets


@app.cell
def _(anywidget, traitlets):
    class MyWidget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            let in_value = model.get("in_value");
            console.log("[debug:init] in_value", in_value);
            model.set("out_value", in_value * 2);
            console.log("[debug:init] out_value", in_value * 2);
            model.save_changes();

            model.on("change:in_value", () => {
                let in_value = model.get("in_value");
                console.log("[debug:change] in_value", in_value);
                model.set("out_value", in_value * 2);
                console.log("[debug:change] out_value", in_value * 2);
                model.save_changes();
            })
        }
        export default { render };
        """
        in_value = traitlets.Int(0).tag(sync=True)
        out_value = traitlets.Int(123).tag(sync=True)
    return (MyWidget,)


@app.cell
def _(MyWidget):
    widget_instance = MyWidget(in_value=8)
    return (widget_instance,)


@app.cell
def _(mo, widget_instance):
    m = mo.ui.anywidget(widget_instance)
    m
    return (m,)


@app.cell
def _(m):
    m.widget.out_value
    return


if __name__ == "__main__":
    app.run()
