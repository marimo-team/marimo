import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# The Mandelbrot Set")
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        This program computes uses an iterative algorithm to visualize the
        [_Mandelbrot set_](https://mathworld.wolfram.com/MandelbrotSet.html),
        the set of complex numbers $c$ for which the sequence defined by the
        iteration

        \[
        z_n = z_{n-1}^2 + c, \quad z_0 = 0
        \]

        is bounded in absolute value.


        In the visualization, every point not in the set is colored by the
        number of iterations the algorithm required to disprove its membership in
        the set. In any iteration, points in the darkest region may
        be in the computed set; once the number of iterations is very high, we
        can be confident that the dark region is the desired Mandelbrot set.
        """
    )
    return


@app.cell
def __(mo, n_max):
    mo.md(
        f"""
        You can play with the number of iterations to see when points are 
        eliminated from the set:

        - _Number of iterations_: {n_max}
        """
    )
    return


@app.cell
def __(mo, reset_plot_scale, x_offset, y_offset, zoom):
    mo.md(
        f"""
        **Plot controls.**

        Here are some controls to play with the plot. ( {reset_plot_scale} )

        - _Zoom_: {zoom}
        - _Pan left/right_: {x_offset}
        - _Pan down/up_: {y_offset}
        """
    )
    return


@app.cell
def __(compute_mandelbrot, n_max, x_offset, y_offset, zoom):
    compute_mandelbrot(n_max.value, 2., 601, 401,
                       zoom=zoom.value,
                       x_offset=x_offset.value,
                       y_offset=y_offset.value)
    return


@app.cell
def __(mo):
    n_max = mo.ui.slider(2, 256, step=1, value=30)
    return n_max,


@app.cell
def __(mo):
    reset_plot_scale = mo.ui.button(label="Click to reset")
    return reset_plot_scale,


@app.cell
def __(mo, reset_plot_scale):
    reset_plot_scale

    zoom = mo.ui.slider(1, 10, step=0.1)
    x_offset = mo.ui.slider(-3, 3, value=0, step=0.01)
    y_offset = mo.ui.slider(-3, 3, value=0, step=0.01)
    return x_offset, y_offset, zoom


@app.cell
def __(np, plt):
    import functools

    @functools.cache
    def compute_mandelbrot(N_max, some_threshold, nx, ny, zoom=1,
                           x_offset=0, y_offset=0):
        # A grid of c-values
        x = np.linspace((-2)/zoom, (1)/zoom, nx)
        y = np.linspace((-1.5)/zoom, (1.5)/zoom, ny)

        c = x[:,np.newaxis] + 1j*y[np.newaxis,:] + x_offset + 1j*y_offset

        # Mandelbrot iteration
        z = c
        mandelbrot_set = np.zeros(z.shape)
        for j in range(N_max):
            z = np.where(np.abs(z) > some_threshold,
                         some_threshold + 1,
                         z**2 + c)

            mask = (abs(z) > some_threshold) * (mandelbrot_set == 0)
            mandelbrot_set[mask] = j**(1/3)

        plt.imshow(
            mandelbrot_set.T, extent=[x[0], x[-1], y[0], y[-1]],
            cmap='viridis',
        )
        plt.colorbar()
        return plt.gca()
    return compute_mandelbrot, functools


@app.cell
def __():
    import numpy as np
    import matplotlib.pyplot as plt
    return np, plt


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
