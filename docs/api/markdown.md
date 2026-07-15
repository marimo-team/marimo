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

## Composing markdown

`mo.md` returns an HTML-like object. When you interpolate it into another
`mo.md(...)` **f-string**, Python stringifies the nested value through
`__format__` before the outer markdown parser runs. That usually works for
plain nested markdown, but it breaks when the nested content must sit inside a
raw HTML block such as `<details>` (CommonMark does not re-parse markdown
inside HTML blocks).

**Working pattern** — use the nested object's `.text` (markdown source) when
embedding into HTML:

```python
_answer = mo.md(
    """
    **The answer**
    """
)

mo.md(
    f"""
    ## Quiz

    <details>
    <summary>Question?</summary>

    {_answer.text}
    </details>
    """
)
```

**Pitfalls**

- `mo.as_html(_answer)` is not the right tool here: `mo.md` is already HTML,
  and wrapping again does not restore markdown parsing inside `<details>`.
- Prefer `.text` for nested markdown source, or build the outer string from
  plain markdown / HTML deliberately.
- Longer term, [PEP 750](https://peps.python.org/pep-0750/) t-strings could let
  `mo.md` receive live objects instead of pre-stringified fragments (Python
  3.14+); until then, compose with `.text` or avoid f-string nesting for
  HTML-wrapped content.

See also the discussion on [#9890](https://github.com/marimo-team/marimo/issues/9890).

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
