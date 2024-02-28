# Table

```{eval-rst}
.. marimo-embed::
    :size: large

    @app.cell
    def __():
        table = mo.ui.table(data=office_characters, pagination=True)
        return

    @app.cell
    def __():
        mo.vstack([table, table.value])
        return

    @app.cell
    def __():
        office_characters = [
            {"first_name": "Michael", "last_name": "Scott"},
            {"first_name": "Jim", "last_name": "Halpert"},
            {"first_name": "Pam", "last_name": "Beesly"},
            {"first_name": "Dwight", "last_name": "Schrute"},
            {"first_name": "Angela", "last_name": "Martin"},
            {"first_name": "Kevin", "last_name": "Malone"},
            {"first_name": "Oscar", "last_name": "Martinez"},
            {"first_name": "Stanley", "last_name": "Hudson"},
            {"first_name": "Phyllis", "last_name": "Vance"},
            {"first_name": "Meredith", "last_name": "Palmer"},
            {"first_name": "Creed", "last_name": "Bratton"},
            {"first_name": "Ryan", "last_name": "Howard"},
            {"first_name": "Kelly", "last_name": "Kapoor"},
            {"first_name": "Toby", "last_name": "Flenderson"},
            {"first_name": "Darryl", "last_name": "Philbin"},
            {"first_name": "Erin", "last_name": "Hannon"},
            {"first_name": "Andy", "last_name": "Bernard"},
            {"first_name": "Jan", "last_name": "Levinson"},
            {"first_name": "David", "last_name": "Wallace"},
            {"first_name": "Holly", "last_name": "Flax"},
        ]
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.table
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.table.table
```
