# Theming

marimo provides basic support for theming. You can include a custom CSS file in your notebook that will be applied to the entire notebook. This allows you to customize the appearance of your notebook to your liking.

To include a custom CSS file, in the configuration dropdown, add the relative file path to your CSS file in the `Custom CSS` field. Once saved, you should see the changes applied to your notebook:

```python
app = marimo.App(css_file="custom.css")
```

## Theming at the project level

You may also set the `custom_css` field in your project configuration to apply a custom CSS file. This theme won't be applied if the notebook is shared with someone else, but it will be applied to all notebooks open inside the project.

```toml
[tool.marimo.display]
custom_css = ["additional.css"]
```

## CSS Variables

We support only a few CSS variables as part of the "public API" for theming. These are:

```css
--marimo-monospace-font
--marimo-text-font
--marimo-heading-font
```

!!! warning "Other CSS Variables"

    We cannot guarantee that other CSS variables or classnames will be stable across versions.

## Example

Here is an example of a custom CSS file that changes the font of the notebook:

```css
/* Load Inter from Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap');

:root {
  --marimo-heading-font: 'Inter', sans-serif;
}

/* Increase paragraph font size and change color */
.paragraph {
  font-size: 1.2rem;
  color: light-dark(navy, pink);
}
```

## Custom HTML Head

You can further customize your notebook by adding custom HTML in the `<head>` section of your notebook. This allows you to add additional functionality to your notebook, such as analytics, custom fonts, meta tags, or external scripts.

See the [Custom HTML Head](html_head.md) guide for more details.

## Forcing dark mode

In order to force a theme for an application, you can override the marimo configuration specifically for an application using the script metadata. See the [Script Configuration](../configuration/index.md#script-metadata-configuration) for more details.

```python
# /// script
# [tool.marimo.display]
# theme = "dark"
# ///
```

## Targeting cells

You can target a cell's styles from the `data-cell-name` attribute. You can also target a cell's output with the `data-cell-role="output"` attribute.

```css
/* Target the cell named "My Cell" */
[data-cell-name='my_cell'] {
  background-color: light-dark(navy, pink);
}

/* Target the output of the cell named "My Cell" */
[data-cell-name='my_cell'] [data-cell-role='output'] {
  background-color: light-dark(navy, pink);
}
```

## Community Themes

The marimo community maintains a [library of custom themes](https://github.com/metaboulie/marimo-themes) that you can use in your notebooks. The library includes various themes like "coldme", "nord", "mininini", and "wigwam", each supporting both light and dark modes.

You can:

- Browse and download existing themes
- Use them in your own notebooks
- Contribute your own themes to share with the community

Visit the [marimo-themes repository](https://github.com/metaboulie/marimo-themes) to explore available themes and learn how to contribute your own.

## More customizations

We want to hear from you! If you have any suggestions for more customization options, please let us know on [GitHub](https://github.com/marimo-team/marimo/discussions)
