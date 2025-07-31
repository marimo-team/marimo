# Control flow

## Controlling when cells run

* Use [`mo.stop`][marimo.stop] to halt execution of a cell when a condition is met.
* Combine [`mo.stop`][marimo.stop] with [`mo.ui.run_button`][marimo.ui.run_button] to gate execution on button click.
* Use [`mo.ui.refresh`][marimo.ui.refresh] to make cells run periodically.

!!! tip "Lazy execution"

    In addition to these utilities, you can [configure the runtime to be lazy](../guides/expensive_notebooks.md#configure-how-marimo-runs-cells), marking cells as stale instead of automatically running them.

::: marimo.stop

## Threading

::: marimo.Thread

::: marimo.current_thread
