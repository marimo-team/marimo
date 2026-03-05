# Python script

Export marimo notebooks to flat Python scripts.

## Export from the marimo editor

You can download your notebook as a Python script from the
notebook menu in the editor (Download > Python).

## Export from the command line

Export to a flat Python script in topological order.

```bash
marimo export script notebook.py -o notebook.script.py
```

!!! warning "Top-level await not supported"

    Exporting to a flat Python script does not support top-level await. If you have
    top-level await in your notebook, you can still execute the notebook as a
    script with `python notebook.py`.

You can then reuse the notebook as a [script](../scripts.md) or a [module](../reusing_functions.md).
