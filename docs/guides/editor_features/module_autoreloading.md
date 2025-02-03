# Module autoreloading

marimo has an advanced module autoreloader built-in, which you can
enable in the [notebook settings](../configuration/runtime_configuration.md).
When you make edits to Python modules that your notebook has imported, the
module autoreloader will automatically mark cells that use them as stale and,
optionally, automatically run them.

!!! question "Why autoreload?"

    Autoreloading enables a workflow that many developers find
    productive: develop complex logic in Python modules, and use the marimo
    notebook as a DAG or main script that orchestrates your logic.

Based on static analysis, the reloader only runs cells affected by your edits.
The reloader is recursive, meaning that marimo tracks modifications for modules
imported by your notebook's imported modules too. These two featuers make
marimo's module autoreloader far more advanced than IPython's.

Autoreloading comes in two types:

1. **autorun**: automatically re-runs cells affected by module modification.

<figure>
<video controls loop width="100%" height="100%" align="center" src="/_static/docs-module-reloading.mp4"> </video>
<figcaption align="center">When set to autorun, marimo's reloader automatically run cells when you edit Python files.</figcaption>
</figure>

2. **lazy**: marks cells affected by module modifications as stale, letting you know which cells need to be re-run.

<figure>
<video controls loop width="100%" height="100%" align="center" src="/_static/docs-module-reloading-lazy.mp4"> </video>
<figcaption align="center">When set to lazy, marimo's reloader marks cells as stale when you edit Python files.</figcaption>
</figure>
