marimo offers many tools for [AI assisted coding](https://docs.marimo.io/guides/editor_features/ai_completion/). However, sometimes you may want to do something more custom and could benefit from a prompt template to get started from. The goal of this page is to share prompts that have proven to be useful and will help you get started on specific tasks. You can add these prompts to your [custom rules](https://docs.marimo.io/guides/editor_features/ai_completion/?h=#custom-rules) but be mindful that doing so will make every call to the LLM more expensive because you're feeding it more tokens. That's why we generally recommend to start your conversations with these snippets if you don't plan on using them very often. 

## Anywidget

Because anywidget is a fairly revent project, LLMs have been known to hallucinate when you try to generate custom widgets from scratch. The following prompt contains an example that helps prevent this behaviour and it also points out common failure scenarios that the LLM shoudl avoid. 

```
When writing an anywidget use vanilla javascript in `_esm` and do not forget about `_css`. The css should look bespoke in light mode and dark mode. Keep the css small unless explicitly asked to go the extra mile. When you display the widget it must be wrapped via `widget = mo.ui.anywidget(OriginalAnywidget())`. 

<example title="Example anywidget implementation">
import anywidget
import traitlets


class CounterWidget(anywidget.AnyWidget):
    _esm = """
    // Define the main render function
    function render({ model, el }) {
      let count = () => model.get("number");
      let btn = document.createElement("button");
      btn.innerHTML = `count is ${count()}`;
      btn.addEventListener("click", () => {
        model.set("number", count() + 1);
        model.save_changes();
      });
      model.on("change:number", () => {
        btn.innerHTML = `count is ${count()}`;
      });
      el.appendChild(btn);
    }
    // Important! We must export at the bottom here!
    export default { render };
    """
    _css = """button{
      font-size: 14px;
    }"""
    number = traitlets.Int(0).tag(sync=True)

widget = mo.ui.anywidget(CounterWidget())
widget

# Grabbing the widget from another cell, `.value` is a dictionary. 
print(widget.value["number"])
</example>

When sharing the anywidget, keep the example minimal. No need to combine it with marimo ui elements unless explicitly stated to do so. 
```

