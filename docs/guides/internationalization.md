# Internationalization (i18n)

marimo provides basic internationalization support through locale configuration. This primarily affects how dates, numbers, and relative times are formatted throughout the interface.

## What is localized

The `locale` setting configures formatting for:

- **Date formatting**: How dates are displayed in data tables and outputs
- **Datetime formatting**: How timestamps are displayed
- **Number formatting**: How numbers are formatted (decimal separators, thousands separators)
- **Relative times**: How relative time expressions like "Today at 8:00 AM" or "Yesterday at 2:30 PM" are displayed

!!! note "Text is not localized"
    marimo does **not** localize UI text, error messages, or documentation as this requires significant effort which we currently cannot afford on our own.

## Configuration

You can configure the locale in three different ways, with the following precedence order:

**Script config > pyproject.toml config > user config**

### User Settings

Configure the locale globally for all notebooks through the Settings menu in the marimo editor:

1. Click the Settings button (⚙️) in the top-right corner
2. Navigate to the "Display" section
3. Set the "Locale" field to your desired locale (e.g., `en-US`, `fr-FR`, `de-DE`)

This setting is stored in your user configuration file (`~/.config/marimo/marimo.toml` or similar).

### Project Configuration (pyproject.toml)

For team projects, you can set the locale in your `pyproject.toml` file to ensure consistency across all team members:

```toml title="pyproject.toml"
[tool.marimo.display]
locale = "en-US"
```

This configuration will apply to all notebooks in the project and override individual user settings.

### Notebook Settings (Script Metadata)

You can also configure the locale for a specific notebook using script metadata. Add this at the top of your notebook file:

```python
# /// script
# [tool.marimo.display]
# locale = "fr-FR"
# ///
```

This has the highest precedence and will override both project and user configurations for that specific notebook.

!!! note "Default behavior"
    If no locale is configured, marimo will use the user's browser locale (detected from `navigator.language`).

## Supported locales

The locale should follow the BCP 47 language tag format (`language-country`).

## Troubleshooting

If your locale setting isn't taking effect:

1. **Check the precedence**: Script metadata overrides pyproject.toml, which overrides user settings
2. **Verify the locale format**: Ensure you're using a valid BCP 47 language tag
3. **Restart marimo**: Some configuration changes may require restarting the marimo server
4. **Check browser support**: The locale must be supported by your browser's `Intl` API

To verify your current configuration, run:

```bash
marimo config show
```

This will display your active configuration including the current locale setting.
