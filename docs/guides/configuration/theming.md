# Theming

marimo provides basic support for theming. You can include a custom CSS file in your notebook that will be applied to the entire notebook. This allows you to customize the appearance of your notebook to your liking.

To include a custom CSS file, in the configuration dropdown, add the relative file path to your CSS file in the `Custom CSS` field. Once saved, you should see the changes applied to your notebook:

```python
app = marimo.App(css_file="custom.css")
```

## CSS Variables

We support only a few CSS variables as part of the "public API" for theming. These are:

```css
--marimo-monospace-font
--marimo-text-font
--marimo-heading-font
```

```{admonition} Other CSS Variables
:class: warning

We cannot guarantee that other CSS variables or classnames will be stable across versions.
```

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

See the [Custom HTML Head](/guides/configuration/html_head.md) guide for more details.

## Community Themes

The marimo community maintains a [library of custom themes](https://github.com/metaboulie/marimo-themes) that you can use in your notebooks. The library includes various themes like "coldme", "nord", "mininini", and "wigwam", each supporting both light and dark modes.

You can:

- Browse and download existing themes
- Use them in your own notebooks
- Contribute your own themes to share with the community

Visit the [marimo-themes repository](https://github.com/metaboulie/marimo-themes) to explore available themes and learn how to contribute your own.

## More customizations

We want to hear from you! If you have any suggestions for more customization options, please let us know on [GitHub](https://github.com/marimo-team/marimo/discussions)
