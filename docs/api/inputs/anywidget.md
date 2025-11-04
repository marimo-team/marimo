
# Building custom UI elements

Build custom UI plugins that hook into marimo's reactive
execution engine by using [anywidget](https://anywidget.dev/).

[anywidget](https://anywidget.dev/) is a Python library and specification for
creating custom Jupyter-compatible widgets. marimo supports anywidget, allowing
you to import anywidget widgets or create your own custom widgets and use them
in your notebooks and apps.

## Importing a widget

You can use anywidgets that others have built, such as
[quak](https://github.com/manzt/quak) or
[drawdata](https://github.com/koaning/drawdata), directly in marimo.

Here is an example using `drawdata`:

```python
# pip install drawdata
from drawdata import ScatterWidget

# Don't forget to wrap the widget with marimo.ui.anywidget
widget = mo.ui.anywidget(ScatterWidget())

# In another cell, you can access the widget's value
widget.value

# You can also access the widget's specific properties
widget.data
widget.data_as_polars
```

For additional examples, see
[our repo](https://github.com/marimo-team/marimo/tree/main/examples/third_party/anywidget) or our [widgets gallery](https://marimo.io/gallery/widgets).

## Custom widget

Anywidget let's you write custom widgets by adding JavaScript to your Python code. Below is an example of a counter widget. 

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

# You can also access the widget's specific properties
widget.count
```
### More examples

If you're eager to build your own widgets and want to dive deeper you may enjoy these resources:

- Before making your own widget, it would be best to check and see if the widget already exists. The [widgets section on the marimo gallery](https://marimo.io/gallery/widgets) as well as the [gallery on anywidget.dev](https://anywidget.dev/en/community/) give you a good overview of what's out there. 
- The [wigglystuff repository](https://github.com/koaning/wigglystuff) has many smaller widgets that could serve as an excellent starting point. 
- We've noticed that coding agents are getting better at generating these anywidgets on the fly. If you're keen to explore that you can check out our [prompts section](/guides/generate_with_ai/prompts/#anywidget) for a quickstart. 
- You may also enjoy [this livestream on the marimo YouTube channel](https://www.youtube.com/watch?v=3V1r5sKnyz8) on building anywidgets. 

---

::: marimo.ui.anywidget
