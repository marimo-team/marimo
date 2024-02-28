# Status

Use progress bars or spinners to visualize loading status in your notebooks and
apps. Useful when iterating over collections or loading data from files,
databases, or APIs.

## Progress bar

You can display a progress bar while iterating over a collection, similar
to `tqdm`.

```{eval-rst}
.. marimo-embed::
    :size: medium

    @app.cell
    def __():
        rerun = mo.ui.button("Rerun")
        rerun
        return

    @app.cell
    async def __():
        import asyncio
        rerun
        for _ in mo.status.progress_bar(
            range(10),
            title="Loading",
            subtitle="Please wait",
            show_eta=True,
            show_rate=True
        ):
            await asyncio.sleep(0.5)
        return
```

```{eval-rst}
.. autofunction:: marimo.status.progress_bar
```

## Spinner

```{eval-rst}
.. marimo-embed::
    :size: medium

    @app.cell
    def __():
        rerun = mo.ui.button("Rerun")
        rerun
        return

    @app.cell
    async def __():
        import asyncio
        rerun
        with mo.status.spinner(title="Loading...") as _spinner:
          await asyncio.sleep(1)
          _spinner.update("Almost done")
          await asyncio.sleep(1)
          _spinner.update("Done")
        return
```

```{eval-rst}
.. autofunction:: marimo.status.spinner
```
