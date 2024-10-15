# Dates

## Single date

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        date = mo.ui.date(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([date, mo.md(f"Has value: {date.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.date
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dates.date
```

## Date and time

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        datetime = mo.ui.datetime(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([datetime, mo.md(f"Has value: {datetime.value}")])
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.datetime
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dates.datetime
```

## Date range

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        date_range = mo.ui.date_range(label="Start Date")
        return

    @app.cell
    def __():
        mo.hstack([date_range, mo.md(f"Has value: {date_range.value}")])
        return
````

```{eval-rst}
.. autoclass:: marimo.ui.date_range
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dates.date_range
```
