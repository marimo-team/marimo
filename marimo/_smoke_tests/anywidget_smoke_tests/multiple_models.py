import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import anywidget

    import ipywidgets
    import traitlets


    class ModelOnlyWidget(ipywidgets.Widget):
        value = traitlets.Int(1).tag(sync=True)


    class Widget(anywidget.AnyWidget):
        _esm = """
        async function render({ model, el }) {

            let fooModel = await model.widget_manager.get_model(
                model.get("foo").slice("IPY_MODEL_".length)
            )
            console.log(fooModel)

            let button = document.createElement("button");
            el.appendChild(button);

            button.innerText = "count is " + fooModel.get("value");

            button.onclick = async () => {
                fooModel.set("value", fooModel.get("value") + 1);
                fooModel.save_changes();
            }

            fooModel.on("change:value", () => {
                button.innerText = "count is " + fooModel.get("value");
            });

        }
        export default { render }
        """
        foo = traitlets.Instance(ModelOnlyWidget).tag(
            sync=True, **ipywidgets.widget_serialization
        )


    m = ModelOnlyWidget()
    mo.ui.anywidget(Widget(foo=m))
    return (m,)


@app.cell
def _(m):
    m.value
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
