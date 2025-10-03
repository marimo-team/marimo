# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anywidget==0.9.13",
#     "marimo",
#     "traitlets==5.14.3",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import anywidget
    import traitlets
    return anywidget, mo, traitlets


@app.cell
def _(anywidget, traitlets):
    class CounterWidget(anywidget.AnyWidget):
        # Widget front-end JavaScript code
        _esm = """
        function render({ model, el }) {
          let getCount = () => model.get("count");
          let button = document.createElement("button");
          button.innerHTML = `count is ${getCount()}`;
          button.addEventListener("click", () => {
            model.set("count", getCount() + 1);
            model.save_changes();
          });
          model.on("change:count", () => {
            button.innerHTML = `count is ${getCount()}`;
          });
          el.appendChild(button);
        }
        export default { render };
      """
        _css = """
        button {
          padding: 5px !important;
          border-radius: 5px !important;
          background-color: #f0f0f0 !important;

          &:hover {
            background-color: lightblue !important;
            color: white !important;
          }
        }
      """

        # Stateful property that can be accessed by JavaScript & Python
        count = traitlets.Int(0).tag(sync=True)
    return (CounterWidget,)


@app.cell
def _(CounterWidget, mo):
    widget = mo.ui.anywidget(CounterWidget())
    return (widget,)


@app.cell
def _(widget):
    widget
    return


if __name__ == "__main__":
    app.run()
