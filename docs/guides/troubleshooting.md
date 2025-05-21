# Troubleshooting

This guide covers common issues and unexpected behaviors you might encounter when using marimo notebooks, along with ways to debug and resolve them. If your issue isn't covered here, try checking our [FAQ](../faq.md).

## Why aren't my cells running?

If you're expecting cells to run in response to changes in other cells, but they're not, consider the following:

### Check for mutations

marimo doesn't track mutations to objects. If you're modifying an object in one cell and expecting another cell to react, this won't work as expected.

Instead of mutating objects across cells, try creating new objects or performing all mutations within the same cell.

[Read more about reactivity](../guides/reactivity.md).

### Verify cell connections

Use the Dependency Panel or Variable Panel to check if your cells are actually connected as you expect.

1. Open the Dependency Panel (graph icon) or Variable Panel (variable icon) in the left sidebar.
2. Look for arrows connecting your cells or check which cells are listed as using each variable.
3. If connections are missing, review your variable usage to ensure cells are properly referencing each other.

<div align="center">
<figure>
<img src="/_static/docs-dependency-graph.png"/>
<figcaption>
Dependency graph showing cell connections.
</figcaption>
</figure>
</div>

## Why is my cell running unexpectedly?

If a cell is running more often than you anticipate:

### Check cell dependencies

Use the Dependency Panel or Variable Panel to see what's triggering your cell:

1. Open the Dependency Panel or Variable Panel.
2. Locate your cell and examine its incoming connections.
3. You might find unexpected dependencies that are causing the cell to run.

### Understand global vs local variables vs functions args

Ensure you're not inadvertently using a global variables when intending to use a local variable or function argument:

1. Check for any variables used in your cell that aren't defined within it.
2. Consider using local variables (prefixed with `_`) for values that shouldn't be consumed by other cells.

## Why is my UI element's value being reset?

If a UI element's value keeps resetting:

### Check that cell defining the UI element isn't rerunning

If the cell defining the UI element reruns, it will reset the element's value to its initial `value` argument. You may be able to avoid this by splitting the UI element definition into a separate cell.

### Use state for persistence

If you need to maintain UI element values across cell runs, consider using `mo.state`:

```python
# Declare state in a separate cell
get_value, set_value = mo.state(initial_value)
```

```python
element = mo.ui.slider(0, 10, value=get_value(), on_change=set_value)
```

This way, the value persists even if the cell defining the element reruns.

## How can I force one cell to run after another?

If you need to ensure a specific execution order:

### Use explicit dependencies

Create an explicit dependency by using a variable from the first cell in the second:

```python
# Cell 1
result = some_computation()
```

```python
# Cell 2
_ = result  # This creates a dependency on Cell 1
further_computation()
```

### Consider refactoring

If you find yourself needing to force execution order often, it might be a sign that your notebook structure could be improved:

1. Try to organize your cells so that natural data flow creates the desired order.
2. Consider combining related operations into single cells where appropriate.

## General debugging tips

### Understanding dependencies

- Use the Variables Panel to inspect variable values and see where they're defined and used.
- Add print statements or use `mo.md()` to output debug information in cell outputs.
- Temporarily disable cells to isolate issues.
- Use the "Lazy" runtime configuration to see which cells are being marked as stale without automatically running them.

Remember, marimo's reactivity is based on global variable definitions and references, and mutations to objects aren't tracked. Keeping this in mind can help you understand and debug unexpected behaviors in your notebooks.

## Patches made by marimo

### Why can't I import a local library?

When using `marimo edit path/to/notebook.py` or `marimo run
path/to/notebook.py`, marimo sets `sys.path` to match what you would get with
`python path/to/notebook.py`. In particular, setting `sys.path[0]` to the notebook
directory:

```
sys.path[0] == 'path/to/'
```

You can add entries to `sys.path` in your pyproject.toml [runtime configuration](../guides/configuration/runtime_configuration.md).

### Other patches

When running as a notebook, marimo makes the following changes to variables:

- marimo patches `pdb.Pdb` with a custom class to enable interactive debugging
  with the `breakpoint()` function
- marimo patches `sys.argv` when running as a notebook to match what you would
  see when [running as a script](../guides/scripts.md).
- local variables currently have their names mangled, meaning source code introspection
  that uses local variables may not work; this behavior may change in the future.

## Why is the notebook returning 404s on the web assets?

If you're seeing 404 errors for web assets like JS or CSS files, it may be due to symlink settings or proxy settings.

### Check symlink settings

If you are using `bazel` or `uv`'s [**link-mode: symlink**](https://docs.astral.sh/uv/reference/settings/#link-mode), you may need to adjust your symlink settings to ensure that web assets are correctly found. By default marimo does not follow symlinks, so you may need to turn this setting on.

Locate your `marimo.toml` configuration file with `marimo config show`, and edit the `follow_symlink` flag:

```toml title="marimo.toml"
[server]
follow_symlink = true
```

### Check proxy settings

If you are using a proxy server, you need to include the `--proxy` flag when running marimo. The proxy will default to port 80 if no port is specified. For example, if your proxy is `example.com` and it uses port 8080, you would run:

```bash
marimo edit --proxy example.com:8080
# or
marimo run --proxy example.com:8080
```

### Reading the logs

marimo will output logs to `$XDG_CACHE_HOME/marimo/logs/*`. To view the logs, run:

```bash
cat $XDG_CACHE_HOME/marimo/logs/github-copilot-lsp.log
```

Available logs are:

- `github-copilot-lsp.log`
- `pylsp.log`
