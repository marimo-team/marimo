# Configuration

marimo offers two types of configuration: User Configuration and App Configuration. Both can be easily managed through the Settings menu in the marimo editor.

## App Configuration

App Configuration is specific to each notebook and is stored in the `notebook.py` file. This allows you to customize various aspects of your notebook, including:

- Notebook width
- Notebook title
- Custom CSS
- Additional app-specific settings
- _and more_

## User Configuration

User Configuration applies globally across all marimo notebooks and is stored in a `.marimo.toml` file. marimo searches for this file in the following order:

1. Current directory
2. Parent directories (moving up the tree)
3. Home directory (`~/.marimo.toml`)

If no `.marimo.toml` file is found, marimo creates a default one in your home directory.

While you can edit the `.marimo.toml` file directly, we recommend using the marimo UI for a more user-friendly experience. To view your current configuration and locate the config file, run:

```bash
marimo config show
```

You can customize:

- [Runtime configuration](/guides/runtime_configuration.md)
- [Hotkeys](/guides/editor_features/hotkeys.md)
- Completion settings (auto-completion, AI copilot, etc.)
- Display settings (theme, font size, output placement, etc.)
- Autosave settings
- Package management preferences
- Server settings
- VIM keybindings
- Formatting settings
- [AI settings](/guides/editor_features/ai_completion.md)
- _and more_
