# Integrating with marimo

These guides will help you integrate your objects with marimo and hook
into marimo's reactive execution engine for UI plugins.

Still need help? Reach out to us on [Discord](https://marimo.io/discord?ref=docs) or
[GitHub issues](https://github.com/marimo-team/marimo/issues).

!!! tip "Checking if running in a marimo notebook"

    You can check if Python is running in a marimo notebook with
    [`mo.running_in_notebook`][marimo.running_in_notebook]. This can be helpful
    when developing library code that integrates with marimo.

| Guide | Description |
|-------|-------------|
| [Displaying Objects](displaying_objects.md) | Richly display objects by hooking into marimo's media viewer |
| [Custom UI Plugins](custom_ui_plugins.md) | Build custom UI plugins that hook into marimo's reactive execution engine |
