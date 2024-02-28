# Dictionary

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        first_name = mo.ui.text(placeholder="First name")
        last_name = mo.ui.text(placeholder="Last name")
        email = mo.ui.text(placeholder="Email", kind="email")

        dictionary = mo.ui.dictionary(
            {
                "First name": first_name,
                "Last name": last_name,
                "Email": email,
            }
        )
        return
    @app.cell
    def __():
        mo.hstack(
          [dictionary, dictionary.value],
          justify="space-between"
        )
        return
```

```{eval-rst}
.. autoclass:: marimo.ui.dictionary
  :members:

  .. autoclasstoc:: marimo._plugins.ui._impl.dictionary.dictionary
```
