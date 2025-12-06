# Dates

## Single date

/// marimo-embed

```python
    @app.cell
    def __():
        date = mo.ui.date(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([date, mo.md(f"Has value: {date.value}")])
        return

```

///

::: marimo.ui.date
  :members:

## Date and time

```python
    @app.cell
    def __():
        datetime = mo.ui.datetime(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([datetime, mo.md(f"Has value: {datetime.value}")])
        return
```

::: marimo.ui.datetime
  :members:

## Date range

/// marimo-embed

```python
    @app.cell
    def __():
        date_range = mo.ui.date_range(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([date_range, mo.md(f"Has value: {date_range.value}")])
        return
```

///

::: marimo.ui.date_range
  :members:

## Date slider

/// marimo-embed

```python
    @app.cell
    def __():
        date_slider = mo.ui.date_slider(
            start="2025-01-01",
            stop="2025-01-15",
        )
        return

    @app.cell
    def __():
        mo.hstack([date_slider, mo.md(f"Has value: {date_slider.value}")])
        return
```

///

::: marimo.ui.date_slider
  :members:
