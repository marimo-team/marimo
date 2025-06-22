import marimo

__generated_with = "0.14.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import plotly.express as px
    import pandas as pd
    import numpy as np
    return mo, pd, px, np


@app.cell
def __(np, pd, px):
    # Create sample data for parallel coordinates
    np.random.seed(42)
    n_samples = 100
    
    data = pd.DataFrame({
        'sepal_length': np.random.normal(5.8, 0.8, n_samples),
        'sepal_width': np.random.normal(3.0, 0.4, n_samples),
        'petal_length': np.random.normal(3.8, 1.8, n_samples),
        'petal_width': np.random.normal(1.2, 0.8, n_samples),
        'species': np.random.choice(['setosa', 'versicolor', 'virginica'], n_samples)
    })
    
    # Create parallel coordinates plot
    fig = px.parallel_coordinates(
        data, 
        color='species',
        dimensions=['sepal_length', 'sepal_width', 'petal_length', 'petal_width'],
        title="Parallel Coordinates Plot - Test Selection"
    )
    
    fig
    return data, fig


@app.cell
def __(fig, mo):
    # Make the plot reactive
    parcoords_plot = mo.ui.plotly(fig)
    parcoords_plot
    return parcoords_plot,


@app.cell
def __(parcoords_plot):
    # Display selection results
    f"""
    ## Selection Results
    
    **Value:** {parcoords_plot.value}
    
    **Ranges:** {parcoords_plot.ranges}
    
    **Points:** {parcoords_plot.points}
    
    **Indices:** {parcoords_plot.indices}
    """
    return


@app.cell
def __(parcoords_plot):
    # Display raw selection data for debugging
    f"**Raw selection data:** {parcoords_plot._selection_data if hasattr(parcoords_plot, '_selection_data') else 'No selection data'}"
    return


if __name__ == "__main__":
    app.run()