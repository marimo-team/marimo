import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Surfaces")
    return


@app.cell
def __(plot_3d_surface, selected_function):
    ax = plot_3d_surface(selected_function)
    return ax,


@app.cell
def __(ax, xlim, ylim, zlim):
    ax.set_xlim(xlim.value)
    ax.set_ylim(ylim.value)
    ax.set_zlim(zlim.value)
    ax
    return


@app.cell
def __(
    a,
    b,
    function,
    mo,
    saddle_param_a,
    saddle_param_b,
    sphere_param_r,
    torus_param_a,
    torus_param_c,
):
    if function.value == "paraboloid":
        _prose = rf"""defined by the function

        \[
        f(x, y) = ax^2 + by^2,
        \]

        where $a={a.value}$ and $b={b.value}$.
        """
    elif function.value == "saddle":
        _prose = rf"""defined by the function

        \[
        f(x, y) = ax^2 - by^4,
        \]

        where $a=${saddle_param_a.value} and $b$={saddle_param_b.value}.
        """
    elif function.value == "sphere":
        _prose = rf"""given by

        \[
        (x, y, z) =
        r \begin{{bmatrix}}
        \cos(\theta)\sin(\phi) \\
        \sin(\theta)\sin(\phi) \\
        \cos(\phi)
        \end{{bmatrix}}
        \]

        where $\theta \in [0, 2\pi]$ and $\phi \in [0, \pi]$ and
        $r={sphere_param_r.value}$ is the radius.
        """
    elif function.value == "torus":
        _prose = rf"""given by

        \[
        (x, y, z) = \begin{{bmatrix}}
        (c + a\cos(v))\cos(u) \\
        (c + a\cos(v))\sin(u) \\
        a\sin(v) \\
        \end{{bmatrix}}
        \]

        where $u \in [0, 2\pi]$ and $v \in [0, 2\pi]$,
        $c={torus_param_c.value}$ is radius of the torus from the origin,
        and $a={torus_param_a.value}$ is inner radius of the torus.
        """
    mo.md(
        rf"""You are looking at a **{function}**. This is a
        surface in $\mathbf{{R}}^3$ {_prose}
        """
    )
    return


@app.cell
def __(function, function_options):
    selected_function = function_options[function.value]
    return selected_function,


@app.cell
def __(paraboloid, saddle, sphere, torus):
    function_options = {
        "paraboloid": paraboloid,
        "saddle": saddle,
        "sphere": sphere,
        "torus": torus,
    }
    return function_options,


@app.cell
def __(mo):
    function = mo.ui.dropdown(
        options=[
            "paraboloid",
            "saddle",
            "sphere",
            "torus"
        ], value='paraboloid'
    )
    return function,


@app.cell
def __(plt):
    def plot_3d_surface(surface_function):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        x, y, z = surface_function()
        ax.plot_surface(x, y, z, cmap='viridis')

        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')

        fig.set_size_inches(7, 7)

        return ax
    return plot_3d_surface,


@app.cell
def __(mo):
    mo.md("### Controls")
    return


@app.cell
def __(function, mo):
    if function.value == "paraboloid":
        _xlim, _ylim, _zlim = (-1, 1), (-1, 1), (0, 2)
    elif function.value == "saddle":
        _xlim, _ylim, _zlim = (-1, 1), (-1, 1), (-1, 1)
    elif function.value == "sphere" or function.value == "torus":
        _xlim, _ylim, _zlim = (-5, 5), (-5, 5), (-5, 5)
    else:
        raise ValueError("Unrecognized function value ", function.value)


    xlim = mo.ui.array([
        mo.ui.number(-10, 10, value=_xlim[0]),
        mo.ui.number(-10, 10, value=_xlim[1]),
    ], label='xlim')
    ylim = mo.ui.array([
        mo.ui.number(-10, 10, value=_ylim[0]),
        mo.ui.number(-10, 10, value=_ylim[1]),
    ], label='ylim')
    zlim = mo.ui.array([
        mo.ui.number(-10, 10, value=_zlim[0]),
        mo.ui.number(-10, 10, value=_zlim[1]),
    ], label='zlim')

    mo.md(
        f"""
        You can adjust the plot using these controls:

        **Axes.**

        {mo.hstack([xlim, ylim, zlim])}
        """
    )
    return xlim, ylim, zlim


@app.cell
def __(function, mo):
    if function.value == "paraboloid":
        a = mo.ui.slider(1, 10)
        b = mo.ui.slider(1, 10)
        _prose = f"""
        - $a$: {a}
        - $b$: {b}
        """
    elif function.value == "saddle":
        saddle_param_a = mo.ui.slider(1, 10)
        saddle_param_b = mo.ui.slider(1, 10)
        _prose = f"""
        - $a$: {saddle_param_a}
        - $b$: {saddle_param_b}
        """
    elif function.value == "sphere":
        sphere_param_r = mo.ui.slider(1, 10)
        _prose = f"""
        - $r$: {sphere_param_r}
        """
    elif function.value == "torus":
        torus_param_c = mo.ui.slider(0, 10, value=1)
        torus_param_a = mo.ui.slider(0.5, 10)
        _prose = f"""
        - $c$: {torus_param_c}
        - $a$: {torus_param_a}
        """
    else:
        _prose = ""

    mo.md("**Parameters.**\n" + _prose) if _prose else None
    return (
        a,
        b,
        saddle_param_a,
        saddle_param_b,
        sphere_param_r,
        torus_param_a,
        torus_param_c,
    )


@app.cell
def __(grid, saddle_param_a, saddle_param_b):
    def saddle():
        x, y = grid(xlim=(-1, 1), ylim=(-1, 1))
        return x, y, saddle_param_a.value*x**2 - saddle_param_b.value*y**4
    return saddle,


@app.cell
def __(a, b, grid):
    def paraboloid():
        x, y = grid(xlim=(-1, 1), ylim=(-1, 1))
        return x, y, a.value*x**2 / 2 + b.value*y**2/ 2
    return paraboloid,


@app.cell
def __(grid, np, sphere_param_r):
    def sphere():
        theta, phi = grid(xlim=(0, 2*np.pi), ylim=(0, np.pi))
        x = np.cos(theta)*np.sin(phi)
        y = np.sin(theta)*np.sin(phi)
        z = np.cos(phi)
        return sphere_param_r.value*x, sphere_param_r.value*y, sphere_param_r.value*z
    return sphere,


@app.cell
def __(grid, np, torus_param_a, torus_param_c):
    def torus():
        theta, phi = grid((0, 2 * np.pi), (0, 2 * np.pi))
        center_radius = torus_param_c.value
        tube_radius = torus_param_a.value

        x = (center_radius + tube_radius*np.cos(theta)) * np.cos(phi)
        y = (center_radius + tube_radius*np.cos(theta)) * np.sin(phi)
        z = tube_radius*np.sin(theta)
        return x, y, z
    return torus,


@app.cell
def __(np):
    def grid(xlim, ylim):
        xmin, xmax = xlim
        ymin, ymax = ylim
        x = np.linspace(xmin, xmax, 100)
        y = np.linspace(ymin, ymax, 100)
        return np.meshgrid(x, y)
    return grid,


@app.cell
def __():
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    import numpy as np
    return Axes3D, np, plt


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
