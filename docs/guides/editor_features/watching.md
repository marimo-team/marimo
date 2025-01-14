# Watching notebooks

marimo's `--watch` flag enables a file watcher that automatically sync your
notebook file with the marimo editor or running application.

This allows you to edit your notebook file in the editor of your choice, and
have the changes automatically reflected in the running editor or application.

!!! tip "Install watchdog for better file watching"
    For better file watching performance, install watchdog with `pip install watchdog`. Without watchdog, marimo will poll for file changes which is less efficient.

## `marimo run --watch`

When you run a notebook with the `--watch` flag, whenever the file watcher
detects a change to the notebook file, the application will be refreshed.
The browser will trigger a page refresh to ensure your notebook starts from a fresh state.

## `marimo watch --watch`

When you edit a notebook file with the `--watch` flag, whenever the file watcher
detects a change to the notebook file, the new cells and code changes will be streamed to
the browser editor.

This code will not be executed until you run the cell, and instead marked as stale.

## Watching for data changes

!!! note
    Support for watching data files and automatically refreshing cells that depend on them is coming soon. Follow along at <https://github.com/marimo-team/marimo/issues/3258>
