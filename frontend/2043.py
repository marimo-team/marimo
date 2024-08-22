import marimo

__generated_with = "0.8.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import anywidget
    import traitlets
    import random
    return anywidget, mo, random, traitlets


@app.cell(hide_code=True)
def __(anywidget, traitlets):
    class CounterWidget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
          const button = document.createElement("button");
          const update = () => {
              button.innerHTML = `${model.get("msg")} ${model.get("count")} (js-none: ${Math.random().toFixed(3)})`;
          };
          button.addEventListener("click", () => {
            model.set("count", model.get("count") + 1);
            model.save_changes();
          });
          update();
          model.on("change:count", update);
          model.on("change:msg", update);
          el.classList.add("counter-widget");
          el.appendChild(button);
        }
        export default { render };
        """
        _css = """
        .counter-widget button { color: white; font-size: 1.75rem; background-color: #ea580c; padding: 0.5rem 1rem; border: none; border-radius: 0.25rem; }
        .counter-widget button:hover { background-color: #9a3412; }
        """
        count = traitlets.Int(0).tag(sync=True)
        msg = traitlets.Unicode("").tag(sync=True)
    return CounterWidget,


@app.cell
def __(mo):
    mo.md(r"""## Just anywidget""")
    return


@app.cell
def __(CounterWidget):
    counter = CounterWidget(count=42, msg="count is")
    return counter,


@app.cell
def __(counter):
    counter
    return


@app.cell
def __(counter, mo, random):
    def _one(v):
        counter.set_trait(
            "msg", f"COUNT IS!! (py-nonce: {random.randint(0, 100)})"
        )


    def _two(v):
        counter.msg = f"COUNT IS!! (py-nonce: {random.randint(0, 100)})"


    one = mo.ui.button(label="set_trait", on_change=_one)
    two = mo.ui.button(label="counter.msg = x", on_change=_two)
    mo.hstack([one, two]).left()
    return one, two


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""## Wrapped in mo.ui.anywidget""")
    return


@app.cell
def __(CounterWidget, mo):
    wrapped_counter = mo.ui.anywidget(CounterWidget(count=42, msg="count is"))
    return wrapped_counter,


@app.cell
def __(wrapped_counter):
    wrapped_counter
    return


@app.cell
def __(mo, random, wrapped_counter):
    def _one(v):
        wrapped_counter.set_trait(
            "msg", f"COUNT IS!! (py-nonce: {random.randint(0, 100)})"
        )


    def _two(v):
        wrapped_counter.msg = f"COUNT IS!! (py-nonce: {random.randint(0, 100)})"


    def _three(v):
        wrapped_counter.widget.msg = (
            f"COUNT IS!! (py-nonce: {random.randint(0, 100)})"
        )


    button_one = mo.ui.button(label="set_trait", on_change=_one)
    button_two = mo.ui.button(label="counter.msg = x", on_change=_two)
    button_three = mo.ui.button(label="counter.widgt.msg = x", on_change=_two)
    mo.hstack([button_one, button_two, button_three]).left()
    return button_one, button_three, button_two


@app.cell
def __(wrapped_counter):
    # Should be: <class '...MarimoComm'>
    type(wrapped_counter.widget.comm)
    return


if __name__ == "__main__":
    app.run()
