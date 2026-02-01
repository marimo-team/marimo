# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.4.1",
#     "drawdata==0.3.4",
#     "marimo",
#     "matplotlib==3.9.2",
#     "numpy==2.1.3",
#     "pandas==2.2.3",
#     "scikit-learn==1.5.2",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
    import sklearn
    from sklearn.pipeline import make_pipeline
    from sklearn.utils import check_array

    np.random.seed(0)
    matplotlib.style.use("ggplot")
    plt.rcParams["figure.figsize"] = [10, 4]
    return mo, np, plt


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Introduction to monotonic splines

    > It turns out that you can generate features that can help turn (linear) machine learning models into models that respent monotonicity. While this technique isn't going to be useful for every application out there, it is a nice exercise in feature engineering because it does show off some lesser known and unconventional techniques.
    >
    > This document reflects the code discussed in [this probabl livestream](https://www.youtube.com/watch?v=BLsWIJSKcGg) which in turn was heavily insired by [this blogpost](https://matekadlicsko.github.io/posts/monotonic-splines/).

    We are going to dive into feature engineering in this document, but before going there it would help to have a dataset first. So let's draw one! **Draw some points below**, but make sure that you only draw a single class of points here. We're going for a regression dataset here where the x-values need to predict the y-values.
    """)
    return


@app.cell
def _(mo):
    from drawdata import ScatterWidget

    widget = mo.ui.anywidget(ScatterWidget())
    widget
    return (widget,)


@app.cell
def _(mo, widget):
    mo.stop(
        not widget.value["data"],
        mo.md("Draw a dataset above to proceed!").callout(),
    )

    df = widget.data_as_pandas.sort_values("x")
    X, y = df[["x"]].values, df["y"].values
    return X, df, y


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## General splines

    You have probably drawn something that is very much non-linear. So you might expect a linear model to perform quite badly here. However, thanks to non-linear feature-engineering, we might still be able to get a nice fit. After all, getting the right features is 90% of the work towards a good model.

    So let's build a pipeline that uses the [SplineTransformer](https://scikit-learn.org/1.5/modules/generated/sklearn.preprocessing.SplineTransformer.html) from scikit-learn. This featurizer can generate "hills" on our behalf that span the input space of the x-axis.
    """)
    return


@app.cell(hide_code=True)
def _(X, np, plt, tfm):
    X_tfm = tfm.fit_transform(X)

    x_range = np.linspace(-50, 900, 2000).reshape(-1, 1)
    x_range_tfm = tfm.transform(x_range)

    plt.plot(x_range, x_range_tfm)
    return X_tfm, x_range, x_range_tfm


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    You can see the x-values that our drawing widget can provide and you can also see all the generated features. Each feature is represented with a different colored line and you should also see how each hill goes up and typically goes back down again. At the edges of the samples that we have we see straight lines in an attempt to also have some features for extrapolation.

    There are some inputs for this `SplineTransformer` though. We can ask the transformer to add more hills, each hill also has a polynomial degree attached to it that we may alter and we can also tell the component to have the placement of each hill be determined by the quantiles in the dataset.

    Feel free to change the drawing and the parameters at this point to try and get a feeling for this.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    n_knots = mo.ui.slider(
        2, 20, step=1, show_value=True, label="number of knots", value=5
    )
    knots = mo.ui.dropdown(["uniform", "quantile"], value="uniform")
    degree = mo.ui.slider(1, 4, step=1, show_value=True, label="degree", value=2)
    mo.vstack([n_knots, degree, knots])
    return degree, knots, n_knots


@app.cell
def _(degree, knots, n_knots):
    from sklearn.preprocessing import SplineTransformer

    tfm = SplineTransformer(
        n_knots=n_knots.value, knots=knots.value, degree=degree.value
    )
    tfm
    return (tfm,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    When you then take these generated features and pass them to a linear model, you should be able to see that we're indeed able to fit a very non-linear curve with a linear model.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ... turn into these features:
    """)
    return


@app.cell
def _(X_tfm, df, y):
    import altair as alt
    from sklearn.linear_model import Ridge

    preds = Ridge().fit(X_tfm, y).predict(X_tfm)

    pltr = df.assign(preds=preds)

    p1 = alt.Chart(pltr).mark_point().encode(x="x", y="y")
    p2 = alt.Chart(pltr).mark_line(color="red").encode(x="x", y="preds")

    (p1 + p2).properties(width=1000)
    return Ridge, alt, pltr


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Towards monotonic features

    But let's now do a trick. We will take the features that we generated and then we will cumsum over each single feature.

    That means that these features ...
    """)
    return


@app.cell
def _(plt, x_range, x_range_tfm):
    plt.plot(x_range, x_range_tfm)
    return


@app.cell
def _(plt, x_range, x_range_tfm):
    plt.plot(x_range, x_range_tfm.cumsum(axis=0))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Note the correspondence between the lines here. The color in the chart above has a direct correspondence with the line below.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    You could wonder ... what would happen if I use these 'cumsum' features? Would I still be able to get a nice fit?

    The chart below shows you the new predictions.
    """)
    return


@app.cell
def _(mo):
    strictly_positive = mo.ui.checkbox(label="Strictly positive")
    show_iso = mo.ui.checkbox(label="Show Isotonic Regression")

    mo.vstack([strictly_positive, show_iso])
    return show_iso, strictly_positive


@app.cell
def _():
    import pandas as pd

    return (pd,)


@app.cell
def _(Ridge, X, X_tfm, alt, pd, pltr, show_iso, strictly_positive, y):
    from sklearn.isotonic import IsotonicRegression

    preds_mono = (
        Ridge(positive=strictly_positive.value)
        .fit(X_tfm.cumsum(axis=0), y)
        .predict(X_tfm.cumsum(axis=0))
    )

    final_df = pd.DataFrame({"preds": preds_mono, "x": X[:, 0]})

    p1_mono = alt.Chart(pltr).mark_point().encode(x="x", y="y")
    p2_mono = alt.Chart(final_df).mark_line(color="red").encode(x="x", y="preds")
    together = p1_mono + p2_mono

    if show_iso.value:
        iso = IsotonicRegression().fit(X, y)
        df_iso = pd.DataFrame({"preds_iso": iso.predict(X), "x": X[:, 0]})
        together += (
            alt.Chart(df_iso)
            .mark_line(color="purple")
            .encode(x="x", y="preds_iso")
        )

    together.properties(width=1000).interactive()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    You can choose to compare the results with a prediction made by an [IsotonicRegression](https://scikit-learn.org/1.5/modules/isotonic.html) model. It may help to appreciate the feature generation technique, especially when you force the linear model to only learn strictly positive weights.

    There are a few things to notice here:

    1. Take the chart with a grain of salt. It does demonstrate the idea, but it does not represent a proper benchmark and we are showing everything being fit on a train set here.
    2. Notice how the feature approach has a slightly more smooth prediction over here compared to the isotonic regressor.
    3. Note that this technique is very general. It can be used on whatever estimator that enables you to learn strictly positive weights.
    """)
    return


if __name__ == "__main__":
    app.run()
