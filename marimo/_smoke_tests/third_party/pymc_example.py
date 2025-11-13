import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import pymc as pm
    import numpy as np
    import time

    # Define a simple model
    with pm.Model() as model:
        # Define a normal distribution
        mu = pm.Normal("mu", mu=0, sigma=1)
        # Sample from the distribution
        obs = pm.Normal("obs", mu=mu, sigma=1, observed=np.random.randn(100))


        # Sample from the posterior using NUTS with NumPyro
        trace = pm.sample(draws=100000, nuts_sampler="numpyro")

    # Returning the trace object for further analysis
    trace
    return


if __name__ == "__main__":
    app.run()
