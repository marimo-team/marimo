# Summary
Stack items vertically, in a column.
Combine with `hstack` to build a grid of items.

# Examples
Build a column of items:
```python
# Build a column of items
mo.vstack([mo.md("..."), mo.ui.text_area()])
```
Build a grid:
```python
# Build a grid.
mo.vstack(
    [
        mo.hstack([mo.md("..."), mo.ui.text_area()]),
        mo.hstack([mo.ui.checkbox(), mo.ui.text(), mo.ui.date()]),
    ]
)
```


# Arguments
| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | `Sequence[object]` | A list of items. |
| `align` | `Literal["start", "end", "center", "stretch"], optional` | Align items horizontally: start, end, center, or stretch. |
| `justify` | `Literal["start", "center", "end", "space-between", "space-around"]` | Justify items vertically: start, center, end, space-between, or space-around. Defaults to "start". |
| `gap` | `float, optional` | Gap between items as a float in rem. 1rem is 16px by default. Defaults to 0.5. |
| `heights` | `Union[Literal["equal"], Sequence[float]], optional` | "equal" to give items equal height; or a list of relative heights with same length as `items`, eg, [1, 2] means the second item is twice as tall as the first; or None for a sensible default. |
| `custom_css` | `dict[str, str], optional` | Custom CSS styles for each column. Keys include:<br>- width<br>- height<br>- background_color<br>- border<br>- border_radius<br>- padding |
| `typeless` | `` | Pass unknown types to the stack. |
| `*args` | `` | positional arguments passed to stack |
| `code_block` | `str` | Render a code block in the stack. <pre><code>mo.vstack(),<br>mo.hstack()</code></pre> |
| `second_code_block` | `str` | Render a second code block in the stack. <pre><code>mo.vstack([])</code></pre> |
| `**kwargs` | `` | keyword arguments passed to stack |

# Returns
| Type | Description |
|------|-------------|
| `Html` | An Html object. |