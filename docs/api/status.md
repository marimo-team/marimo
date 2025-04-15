# Status

Use progress bars or spinners to visualize loading status in your notebooks and
apps. Useful when iterating over collections or loading data from files,
databases, or APIs.

## Progress bar

You can display a progress bar while iterating over a collection, similar
to `tqdm`.

/// marimo-embed-file
    size: medium
    filepath: examples/outputs/progress_bar.py
///

::: marimo.status.progress_bar

## Spinner

/// marimo-embed-file
    size: medium
    filepath: examples/outputs/spinner.py
///

::: marimo.status.spinner

