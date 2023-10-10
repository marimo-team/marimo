# Loading

Many use-cases in marimo involve iterating over collections and performing
expensive calculation, or loading data from files, databases, or APIs. For
such cases, marimo provides utilities to communicate loading states to the
end-user (perhaps yourself, if you're running experiments, or someone else
using your tool!).

## Progress bar

You can display a progress bar while iterating over a collection, similar
to `tqdm`.

```{eval-rst}
.. autofunction:: marimo.loading.progress_bar
```

## Spinner

```{eval-rst}
.. autofunction:: marimo.loading.spinner
```

