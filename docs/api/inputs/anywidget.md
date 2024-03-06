# AnyWidget

[AnyWidget](https://anywidget.dev/) is a Python library and specification for creating custom Jupyter-compatible widgets. marimo supports AnyWidget, allowing you to import AnyWidget widgets or create your own custom widgets and use them in your notebooks and apps.

## Custom widget

```python
import anywidget
import traitlets
import marimo as mo

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

widget = mo.ui.anywidget(CounterWidget())


# In another cell, you can access the widget's value
widget.value
```

## Importing a widget

```python
# pip install drawdata
from drawdata import ScatterWidget

widget mo.ui.anywidget(ScatterWidget())

# In another cell, you can access the widget's value
widget.value
```

---

```{eval-rst}
.. autoclass:: marimo.ui.anywidget
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.from_anywidget.anywidget
```
