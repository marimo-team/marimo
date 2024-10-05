# Coming from Jupyter

If you're coming from Jupyter, here are a few tips to help you adapt to marimo
notebooks.

## Runtime configuration

You can [configure marimo's runtime](/guides/configuration/runtime_configuration.md) to not
autorun on startup or on cell execution.

Even when autorun is disabled, your notebook remains a directed graph, with
marimo eliminating hidden state for you and marking cells as stale.

## HTML snapshots

marimo stores notebooks as Python, not JSON. This lets you version notebooks
with git, [execute them as scripts](/guides/scripts.md), and import named
cells into other Python files. However, it does mean that your notebook outputs
(e.g., plots) are not stored in the file.

If you'd like to keep a visual record of your notebook work, [enable
the "Auto-download as HTML" setting](/guides/configuration), which will
periodically snapshot your notebook as HTML to a `__marimo__` folder in the
notebook directory.


## Interactive guide

This guide contains additional tips to help you adapt to marimo. Fun fact: the
guide is itself a marimo notebook!


<iframe src="https://marimo.app/l/z0aerp?embed=true" class="demo xxlarge" frameBorder="0">
</iframe>
