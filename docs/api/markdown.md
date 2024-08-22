# Markdown

Write markdown with `mo.md`; make your markdown **interactive**, **dynamic**,
and **visually rich** by interpolating arbitrary Python values and marimo
elements.

```{eval-rst}
.. autofunction:: marimo.md
```

## Icons

You can render icons from [Iconify](https://icon-sets.iconify.design/) with `mo.icon`.

```{eval-rst}
.. autofunction:: marimo.icon
```

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
