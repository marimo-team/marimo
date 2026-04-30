import marimo

__generated_with = "0.23.3"
app = marimo.App()


@app.cell
def inputs():
    """Declare the dataflow inputs.

    These are real `mo.ui` elements: drag the slider in the editor and the
    notebook re-runs reactively. Hit the dataflow API endpoint and the same
    elements get remote-controlled. Either way, downstream cells consume
    `category.value` and `threshold.value`.
    """
    import marimo as mo

    threshold = mo.api.input(
        min=0,
        max=100,
        default=20,
        description="Minimum value filter",
    )
    category = mo.api.input(
        options=["all", "A", "B", "C"],
        default="all",
        description="Category filter",
    )
    send = mo.api.input(
        ui=mo.ui.run_button(label="Send notifications"),
        description="Send notifications for the filtered rows",
    )
    return category, mo, send, threshold


@app.cell
def load_data(category, threshold):
    """Simulate loading and filtering data based on inputs."""
    import random

    random.seed(42)
    raw_data = [
        {
            "id": i,
            "category": random.choice(["A", "B", "C"]),
            "value": random.randint(1, 100),
        }
        for i in range(50)
    ]

    filtered = [row for row in raw_data if row["value"] >= threshold.value]
    if category.value != "all":
        filtered = [
            row for row in filtered if row["category"] == category.value
        ]
    return (filtered,)


@app.cell
def compute_stats(filtered):
    """Compute summary statistics from the filtered data."""
    if not filtered:
        stats = {"count": 0, "mean": 0, "max": 0, "min": 0}
    else:
        _vals = [row["value"] for row in filtered]
        stats = {
            "count": len(_vals),
            "mean": round(sum(_vals) / len(_vals), 2),
            "max": max(_vals),
            "min": min(_vals),
        }
    return (stats,)


@app.cell
def compute_histogram(filtered):
    """Compute a histogram of values (10-bucket)."""
    if not filtered:
        histogram = []
    else:
        _vals = [row["value"] for row in filtered]
        _bucket_size = 10
        _buckets: dict[str, int] = {}
        for _v in _vals:
            _bucket = (_v // _bucket_size) * _bucket_size
            _label = f"{_bucket}-{_bucket + _bucket_size - 1}"
            _buckets[_label] = _buckets.get(_label, 0) + 1
        histogram = [
            {"bucket": k, "count": v} for k, v in sorted(_buckets.items())
        ]
    return


@app.cell
def format_table(filtered):
    """Format the filtered data as a table for display."""
    table = filtered[:20]
    return (table,)


@app.cell
def send_notifications(filtered, mo, send):
    """Side-effect cell — fires only when the run button is clicked.

    This is the canonical "trigger" pattern: a `mo.ui.run_button` gated by
    `mo.stop` so the cell never auto-runs as part of the reactive graph,
    even when its other refs (`filtered`) change. Subscribe to `n_sent`
    via the dataflow API to surface confirmation in the React app.
    """
    mo.stop(not send.value)
    # Replace with the real side effect (db write, email send, ...).
    n_sent = len(filtered)
    return


@app.cell
def display(category, mo, send, stats, table, threshold):
    """Render a debug view of the inputs and outputs in the editor."""
    mo.vstack(
        [
            mo.md("### Inputs"),
            threshold,
            category,
            send,
            mo.md("### Stats"),
            mo.md(f"`{stats}`"),
            mo.md("### Sample rows"),
            mo.ui.table(table),
        ]
    )
    return


@app.cell
def _(threshold):
    # a slow thing that uses the input but isn't in the app
    import time

    time.sleep(0.5)
    slow_threshold = threshold.value
    slow_threshold
    return


if __name__ == "__main__":
    app.run()
