# Markdown

Write markdown with `mo.md`; make your markdown **interactive**, **dynamic**,
and **visually rich** by interpolating arbitrary Python values and marimo
elements.

::: marimo.md

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
