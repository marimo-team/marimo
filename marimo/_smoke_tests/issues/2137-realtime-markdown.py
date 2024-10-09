import marimo

__generated_with = "0.8.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(time):
    time.sleep(10)
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        ### Realtime Markdown Editing
        Everything you type should update the cell output in realtime, which is pretty cool!

        | Feature           | Description                                            |
        |-------------------|--------------------------------------------------------|
        | Compact Size      | Small and versatile for display in various containers. |
        | Easy Maintenance  | Requires minimal care and indirect sunlight.           |
        | Unique Appearance | Spherical and soft, visually distinct.                 |
        | Oxygen Production | Helps oxygenate aquatic environments.                  |
        | Slow Growth       | Grows about 5 mm per year, keeping size manageable.    |
        | Longevity         | Can live for many years, even over a century.          |
        | Cultural Symbol   | In Japan, seen as good luck charms.                    |
        | Adaptable         | Thrives in various water conditions.                   |
        | Non-Invasive      | Won't overtake the environment like other plants.      |
        | Eco-Friendly      | Sustainable and environmentally safe.                  |

        ![](https://marimo.io/apple-touch-icon.png)
        """
    )
    return


if __name__ == "__main__":
    app.run()
