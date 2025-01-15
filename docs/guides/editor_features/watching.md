# Using your own editor

While we recommend using the [marimo editor](editor_features/index.md),
we understand that you may prefer to use your own own. marimo provides a
`--watch` flag that watches your notebook file for changes, syncing them to
the marimo editor or running application. This lets you to edit your notebook
using an editor of your choice, like neovim, VSCode, Cursor, or PyCharm, and
have the changes automatically reflected in your browser.

!!! tip "Install watchdog for better file watching"
    For better performance, install [watchdog](https://pypi.org/project/watchdog/).
    Without watchdog, marimo resorts to polling.

## `marimo edit --watch`

When you run `marimo edit` with the `--watch` flag, the marimo server
will open your notebook in the browser and watch the underlying notebook
file for changes. When you make changes to the notebook file, they will be
streamed to the marimo editor in the browser.

Synced code will not be executed automatically, with cells marked as stale instead.
Run all stale cells with the marimo editor's "Run" button, or the [`runStale`
hotkey](hotkeys.md), to see the new outputs.

!!! note "Cell signature and returns"
    Don't worry about maintaining the signatures of cells and their return
    values; marimo will handle this for you.

## `marimo run --watch`

When you run a notebook with the `--watch` flag, whenever the file watcher
detects a change to the notebook file, the application will be refreshed. The
browser will trigger a page refresh to ensure your notebook starts from a fresh
state.

## Watching for changes to other modules

marimo can also watch for changes to Python modules that your notebook imports,
letting you edit auxiliary Python files in your own editor as well. Learn how
to enable this feature in our [Module Autoreloading
Guide](module_autoreloading.md)

## Watching for data changes

!!! note
    Support for watching data files and automatically refreshing cells that depend on them is coming soon. Follow along at <https://github.com/marimo-team/marimo/issues/3258>

