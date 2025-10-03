# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.accordion(
        {
            """**e)** Would you say that work, education, and age explain much of the variation in sleep? What other factors could affect the time spent sleeping? Are these factors likely to be correlated with work?""": """
        - The $R^2 = 0.113$ is low
        - Only 11.3% of the variability in sleep is explained by the explanatory variables chosen for the model
        - There are factors left out of the model that may influence sleep. Examples:
            - _Stress_
            - Age of children
            - Profession
        """
        }
    )
    return


@app.cell
def _(mo):
    mo.accordion(
        {
            r"""**a)** Estimate the coefficients of the regression of $Y$ on $X_1$, as well as the standard error of the regression and $R^2$. What do you think of the estimate of $\beta_1$?""": mo.md(
                """
                - By entering the command `regress Y X1` we obtain the estimation below
                - The estimate for $\beta_1$ is unexpected, as it contradicts the economic theory that there is a negative relationship between price and sales.
                """
            )
        }
    )
    return


@app.cell
def _(mo):
    mo.md(r"""**b)** If the expected value of $X$ is the average of its two values mentioned in the previous part, what do you think the expected value of $Y$ will be? Confirm your answer using the law of iterated expectations.""")
    return


@app.cell
def _(mo):
    mo.accordion(
        {
            """**b)** If the expected value of $X$ is the average of its two values mentioned in the previous part, what do you think the expected value of $Y$ will be? Confirm your answer using the law of iterated expectations.""": mo.md("""
    		$$\\mathbb{{E}}\\left[Y \\middle| X = \\frac{{800 + 1400}}{{2}}\\right] = \\mathbb{{E}}\\left[Y | X = 1100\\right] = 0.7 + 0.002 \\times 1100$$

            We can confirm the law of iterated expectations:
            """)
        }
    )
    return


if __name__ == "__main__":
    app.run()
