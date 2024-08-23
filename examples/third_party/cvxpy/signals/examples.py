import marimo

__generated_with = "0.0.1a0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Examples")
    return


@app.cell
def _(mo):
    mo.md("## Real Data")
    return


@app.cell
def _(mo):
    mo.md("### NOAA CO2")
    return


@app.cell
def _(dataloaders, mo, plt):
    co2_df = dataloaders.get_c02_data()

    plt.figure(figsize=(6, 3))
    co2_df.plot(y="average", x="decimal", ax=plt.gca())
    plt.tight_layout()
    mo.tree([co2_df.head(2), plt.gca()], label="data")
    return co2_df,


@app.cell
def _(co2_df, mo, solutions):
    co2_problem = solutions.co2_problem(co2_df)
    co2_problem.decompose()
    mo.tree(
        [co2_problem.plot_decomposition(figsize=(6, 5))], label="decomposition"
    )
    return co2_problem,


@app.cell
def _(co2_df, co2_problem, mo, plt):
    co2_df.plot(y="average", x="decimal")
    plt.figure(figsize=(6, 3))
    plt.plot(co2_df["decimal"], co2_problem.decomposition[1])
    plt.legend(["measured weekly average", "long-term trend"])
    plt.tight_layout()
    mo.tree([plt.gca()], "long-term trend")
    return


@app.cell
def _(mo):
    mo.md("### Solar power generation")
    return


@app.cell
def _(dataloaders, mo, plt):
    pv_df = dataloaders.get_pvdaq_data()
    _fig = pv_df.loc[:"2011-01-15"].plot(y="dc_power", figsize=(6, 3))
    plt.tight_layout()
    mo.tree(
        [
            pv_df.head(2),
            _fig,
        ],
        label="data",
    )
    return pv_df,


@app.cell
def _(mo, pv_df, solutions):
    pv_problem = solutions.pvdaq_problem(pv_df)
    pv_problem.decompose()
    mo.tree(
        [pv_problem.plot_decomposition(exponentiate=True, figsize=(6, 5))],
        label="decomposition",
    )
    return pv_problem,


@app.cell
def _(mo):
    mo.md("## Synthetic Data")
    return


@app.cell
def _(mo):
    mo.md("### Basic changepoint detection")
    return


@app.cell
def _(dataloaders, mo, plt):
    bcd_y, bcd_X_real = dataloaders.make_changepoint_data()
    plt.figure(figsize=(6.5, 3))
    plt.plot(bcd_y, label="observed data, $y$")
    plt.plot(bcd_X_real[1], label="true denoised signal")
    plt.legend()
    mo.tree([plt.gca()], "data")
    return bcd_X_real, bcd_y


@app.cell
def _(mo):
    mo.md("**Exact, nonconvex version**")
    return


@app.cell
def _(bcd_X_real, bcd_y, mo, solutions):
    bcd_problem_ncvx = solutions.basic_changepoint_problem_exact(bcd_y)
    bcd_problem_ncvx.decompose()
    mo.tree(
        [
            bcd_problem_ncvx.plot_decomposition(
                X_real=bcd_X_real, figsize=(6, 5)
            )
        ],
        label="decomposition",
    )
    return bcd_problem_ncvx,


@app.cell
def _(mo):
    mo.md("**Heuristic, convex version**")
    return


@app.cell
def _(bcd_X_real, bcd_y, mo, solutions):
    bcd_problem = solutions.basic_changepoint_problem_heuristic(bcd_y)
    bcd_problem.decompose()
    mo.tree(
        [bcd_problem.plot_decomposition(X_real=bcd_X_real, figsize=(6, 5))],
        "decomposition",
    )
    return bcd_problem,


@app.cell
def _(mo):
    mo.md("### Harder changepoint detection")
    return


@app.cell
def _(dataloaders, mo, plt):
    hcd_y, hcd_X_real = dataloaders.make_changepoint_data(
        include_periodic_component=True
    )
    plt.figure(figsize=(6, 3))
    plt.plot(hcd_y, label="observed data, $y$")
    plt.plot(hcd_X_real[1] + hcd_X_real[2], label="true denoised signal")
    plt.legend()
    plt.tight_layout()
    mo.tree([plt.gca()], "data")
    return hcd_X_real, hcd_y


@app.cell
def _(hcd_X_real, hcd_y, mo, solutions):
    hcd_problem = solutions.hard_changepoint_problem(hcd_y)
    hcd_problem.decompose()
    mo.tree(
        [hcd_problem.plot_decomposition(X_real=hcd_X_real, figsize=(6, 5))],
        "decomposition",
    )
    return hcd_problem,


@app.cell
def _(mo):
    mo.md("### Synthetic soiling data")
    return


@app.cell
def _(dataloaders, mo, plt):
    ss_df, _name = dataloaders.make_soiling_data()
    plt.figure(figsize=(6, 3))
    plt.scatter(ss_df.index, ss_df.daily_norm, 5, alpha=0.5, label="data, $y$")
    plt.plot(
        ss_df.index,
        ss_df.PI_no_noise,
        "k",
        alpha=0.5,
        label="true signal with no noise",
    )
    plt.ylim(0.6, 1.06)
    plt.legend(loc=3)
    plt.title(_name)
    mo.tree([plt.gca()], label="data")
    return ss_df,


@app.cell
def _(mo, np, plt, solutions, ss_df):
    ss_problem, _xr = solutions.soiling_problem(ss_df)
    ss_problem.decompose()
    _fig = ss_problem.plot_decomposition(X_real=_xr, figsize=(6, 12))
    _avg = np.average(ss_problem.decomposition[1])
    _fig.axes[1].set_ylim(_avg - 2.5, _avg + 2.5)
    plt.tight_layout()
    mo.tree([plt.gca()], "decomposition")
    return ss_problem,


@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    import modules.dataloaders as dataloaders
    import modules.solutions as solutions
    return dataloaders, np, pd, plt, solutions


@app.cell
def _():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
