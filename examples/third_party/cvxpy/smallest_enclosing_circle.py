import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """
        # Smallest Enclosing Circle

        This program computes the circle of smallest radius that encloses a given
        randomly sampled set of circles. This is a generalization of the 
        [smallest-circle problem](https://en.wikipedia.org/wiki/Smallest-circle_problem).

        We solve this problem using [CVXPY](https://www.cvxpy.org), a Python library for specifying and
        solving convex optimization problems.

        _Use the slider below to choose the number of circles to sample:_
        """
    )
    return


@app.cell
def __(mo):
    number_of_circles = mo.ui.slider(
        1, 15, value=3, label='Number of circles')
    number_of_circles
    return number_of_circles,


@app.cell
def __(mo, number_of_circles):
    resample_button = mo.ui.button(label='Click this button')
    mo.md(
        f"""
        {resample_button} to solve this problem for another set of
        {number_of_circles.value} circles.
        """
    )
    return resample_button,


@app.cell
def __(np):
    def generate_circles(number_of_circles):
        circles = []
        for i in range(number_of_circles):
            c_i = np.random.randn(2)
            r_i = np.abs(np.random.randn())
            circles.append((c_i, r_i))
        return circles
    return generate_circles,


@app.cell
def __(generate_circles, number_of_circles, resample_button):
    resample_button

    circles = generate_circles(number_of_circles.value)
    return circles,


@app.cell
def __(circles, smallest_enclosing_circle):
    center, radius = smallest_enclosing_circle(circles)
    return center, radius


@app.cell
def __(center, circles, plot_circle, plt, radius):
    for (c_i, r_i) in circles:
        plot_circle(c_i, r_i, color='gray')
    plot_circle(center, radius, color='green', label='smallest enclosing circle')
    plt.xlim(-5, 5)
    plt.ylim(-5, 5)
    plt.legend(loc='upper right')
    plt.gcf().set_size_inches((6, 6))
    plt.gca()
    return c_i, r_i


@app.cell
def __(plt):
    def plot_circle(center, radius, ax=None, **kwargs):
        ax = plt.gca() if ax is None else ax
        ax.add_patch(plt.Circle(center, radius, fill=False, **kwargs))
        return ax
    return plot_circle,


@app.cell
def __(mo):
    mo.md("## The solution method")
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        We can write down a convex optimization problem whose solution gives us
        the smallest circle enclosing the $n$ given circles. Once we do this,
        we can just code up the problem in CVXPY to obtain a solution.

        Here's the problem:

        We seek a circle, parameterized by a center $c = (x, y) \in \mathbf{R}^2$
        and a radius $r \in \mathbf{R}$ satisfying

        \[
        \begin{equation*}
        \begin{array}{ll}
        \text{minimize} & r \\
        \text{subject to } & \|c - c_i\|_2 + r_i \leq r, \quad i=1, \ldots, n,
        \end{array}
        \end{equation*}
        \]

        where $c_1, \ldots, c_n$ and $r_1, \ldots, r_n$ are the centers and radii
        of the $n$ given circles.

        And here's the code:

        ```python3
        def smallest_enclosing_circle(circles):
            radius = cp.Variable()
            center = cp.Variable(2)
            constraints = [
              cp.norm(center - c_i) + r_i <= radius
              for (c_i, r_i) in circles
            ]
            objective = cp.Minimize(radius)
            cp.Problem(objective, constraints).solve()
            return (center.value, radius.value)
        ```
        """
    )
    return


@app.cell
def __(cp):
    def smallest_enclosing_circle(circles):
        radius = cp.Variable()
        center = cp.Variable(2)
        constraints = [
          cp.norm(center - c_i) + r_i <= radius
          for (c_i, r_i) in circles
        ]
        objective = cp.Minimize(radius)
        cp.Problem(objective, constraints).solve()
        return (center.value, radius.value)
    return smallest_enclosing_circle,


@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np
    import cvxpy as cp
    return cp, np, plt


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
