# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Dynamic Selection Analysis

        Create interactive plots with dynamic statistics.
        Common usage: Real-time analysis of selected data points.
        Commonly used in: Exploratory data analysis, outlier detection.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    from holoviews import streams
    
    hv.extension('bokeh')
    
    # Generate sample data
    np.random.seed(42)
    points = hv.Points(np.random.multivariate_normal(
        (0, 0), [[1, 0.1], [0.1, 1]], (1000,)
    ))
    
    # Create selection stream
    selection = streams.Selection1D(source=points)
    
    # Dynamic computation of statistics for selected points
    def selected_info(index):
        selected = points.iloc[index]
        if index:
            mean_vals = selected.array().mean(axis=0)
            label = f'Selection Mean: ({mean_vals[0]:.2f}, {mean_vals[1]:.2f})'
            return selected.relabel(label).opts(
                color='red',
                size=8,
                alpha=0.6
            )
        return hv.Points([]).relabel('No Selection')
    
    # Create dynamic map for selection
    dmap = hv.DynamicMap(selected_info, streams=[selection])
    
    # Combine original points with selection
    plot = (points * dmap).opts(
        hv.opts.Points(
            tools=['box_select', 'lasso_select'],
            size=4,
            alpha=0.6,
            width=500,
            height=400,
            title='Interactive Point Selection'
        )
    )
    
    plot
    return dmap, plot, points, selection


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
