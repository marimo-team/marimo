# /// script
# dependencies = [
#     "holoviews==1.22.1",
#     "marimo",
#     "numpy",
# ]
# requires-python = ">=3.12"
# ///

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    # Taken directly from https://holoviews.org/reference/streams/bokeh/Selection1D_points.html#selection1d-points

    import numpy as np

    import holoviews as hv
    from holoviews import opts, streams

    hv.extension("bokeh")

    opts.defaults(opts.Points(tools=["box_select", "lasso_select"]))

    # Declare some points
    points = hv.Points(np.random.randn(1000, 2))

    # Declare points as source of selection stream
    selection = streams.Selection1D(source=points)

    # Write function that uses the selection indices to slice points and compute stats
    def selected_info(index):
        selected = points.iloc[index]
        if index:
            label = "Mean x, y: {:.3f}, {:.3f}".format(
                *tuple(selected.array().mean(axis=0))
            )
        else:
            label = "No selection"
        return selected.relabel(label).opts(color="red")

    # Combine points and DynamicMap
    points + hv.DynamicMap(selected_info, streams=[selection])
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
