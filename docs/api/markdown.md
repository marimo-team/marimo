# Markdown

Write markdown with `mo.md`; make your markdown **interactive**, **dynamic**,
and **visually rich** by interpolating arbitrary Python values and marimo
elements.

::: marimo.md

## Loading LaTeX macros

You can load LaTeX macros using `mo.latex(filename=...)`.

::: marimo.latex

!!! warning "Side effects"
    The `mo.latex()` function has side effects (registering the LaTeX macros) and should be used in the same cell as `import marimo`. Otherwise, the LaTeX macros may not be loaded before the cells that use them.

## Icons

We support rendering icons from [Iconify](https://icon-sets.iconify.design/).

When is inside markdown, you can render an icon with the syntax `::iconset:icon-name::` for example `::lucide:rocket::` or `::mdi:home::`. This is useful for quickly adding an icon, however, it does not support advanced configuration such as size, color, and rotation.

For other advanced features, use `mo.icon()` such as `mo.icon("lucide:rocket", size=20)` or `mo.icon("mdi:home", color="blue")`.

::: marimo.icon

## Tooltips

You can render a tooltip by adding the `data-tooltip` attribute to an element.

```python
mo.md(
    '''
    <div data-tooltip="This is a tooltip">Hover over me</div>
    '''
)
mo.ui.button(
    label='<div data-tooltip="This is a tooltip">Hover over me</div>'
)
```

## Rendering images

You can render images from a local `public/` folder:

```python
mo.md(
    '''
    <img src="public/image.png" width="100" />
    '''
)
```

See [Static files](../guides/outputs.md#static-files) for information about serving images and other static assets.
