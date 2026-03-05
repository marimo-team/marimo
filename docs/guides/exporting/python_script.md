# Python script

Export marimo notebooks to flat Python scripts.

## Export from the command line

Export to a flat Python script in topological order, so the cells adhere to
their dependency graph.

```bash
marimo export script notebook.py -o notebook.script.py
```

!!! warning "Top-level await not supported"

    Exporting to a flat Python script does not support top-level await. If you have
    top-level await in your notebook, you can still execute the notebook as a
    script with `python notebook.py`.
