# Integrating with marimo

```{eval-rst}
.. toctree::
  :maxdepth: 2
  :hidden:

  displaying_objects
  custom_ui_plugins
```

These guides will help you integrate your objects with marimo and hook
into marimo's reactive execution engine for UI plugins.

Still need help? Reach out to us on [Discord](https://discord.gg/JE7nhX6mD8) or
[GitHub issues](https://github.com/marimo-team/marimo/issues).

```{admonition} Checking if running in a marimo notebook
:class: tip

You can check if Python is running in a marimo notebook with
[`mo.running_in_notebook`](#marimo.running_in_notebook). This can be helpful
when developing library code that integrates with marimo.
```

|                           |                                                                           |
| :------------------------ | :------------------------------------------------------------------------ |
| {doc}`displaying_objects` | Richly display objects by hooking into marimo's media viewer              |
| {doc}`custom_ui_plugins`  | Build custom UI plugins that hook into marimo's reactive execution engine |
