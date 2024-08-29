# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "matplotlib",
#     "numpy",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np
    import marimo as mo

    return mo, np, plt


@app.cell
def __(mo, plt):
    mo.ui.table(plt.style.available, selection=None, page_size=2)
    return


@app.cell
def __(create_plot, plt):
    plt.style.use('default')
    create_plot().gca()
    return


@app.cell
def __(create_plot, plt):
    plt.style.use('dark_background')
    create_plot().gca()
    return


@app.cell
def __(np, plt):
    def create_plot():    
        # Create sample data
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.cos(x)
        y3 = np.tan(x)
        y4 = x**2
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot multiple lines without specifying colors
        ax.plot(x, y1, label='Sin')
        ax.plot(x, y2, label='Cos')
        ax.plot(x, y3, label='Tan')
        ax.plot(x, y4, label='x^2')
        
        # Customize the plot
        ax.set_title('Dark Mode Plot with Auto Colors')
        ax.set_xlabel('X-axis')
        ax.set_ylabel('Y-axis')
        ax.legend()
        
        # Add a grid
        ax.grid(True, linestyle='--', alpha=0.7)
        
        return plt
    return create_plot,


if __name__ == "__main__":
    app.run()
