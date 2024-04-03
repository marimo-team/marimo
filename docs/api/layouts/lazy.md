# Lazy

```{eval-rst}
.. marimo-embed::
    @app.cell
    def __():
        mo.accordion({
            "Open me": mo.lazy(expensive_number, show_loading_indicator=True)
        })
        return

    @app.cell
    def __():
        import time

        def expensive_number():
            time.sleep(1)
            num = random.randint(0, 100)
            return num
        return
```

```{eval-rst}
.. autofunction:: marimo.lazy
```
