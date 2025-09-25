# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anywidget==0.9.18",
#     "numpy==2.3.3",
#     "polars==1.33.1",
#     "traitlets==5.14.3",
#     "uchimata==0.3.0",
# ]
# ///

import marimo

__generated_with = "0.16.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import anywidget
    import traitlets

    class Widget(anywidget.AnyWidget):
        _esm = """
        export default {
          render({ model, el }) {
              const dataView = model.get("data");
              const bytes = new Uint8Array(dataView.buffer)
              const decoded = new TextDecoder().decode(bytes);
              el.innerText = decoded;
          }
        }
        """
        data = traitlets.Any().tag(sync=True)

    # Should display "hello"
    Widget(data=b"hello")
    return


@app.cell
def _():
    import uchimata as uchi
    import numpy as np

    BINS_NUM = 1000

    # Step 1: Generate random structure, returns a 2D numpy array:
    def make_random_3D_chromatin_structure(n):
        position = np.array([0.0, 0.0, 0.0])
        positions = [position.copy()]
        for _ in range(n):
            step = np.random.choice(
                [-1.0, 0.0, 1.0], size=3
            )  # Randomly choose to move left, right, up, down, forward, or backward
            position += step
            positions.append(position.copy())
        return np.array(positions)

    random_structure = make_random_3D_chromatin_structure(BINS_NUM)

    # Step 2: Display the structure in an uchimata widget
    numbers = list(range(0, BINS_NUM + 1))
    vc = {
        "color": {
            "values": numbers,
            "min": 0,
            "max": BINS_NUM,
            "colorScale": "Spectral",
        },
        "scale": 0.01,
        "links": True,
        "mark": "sphere",
    }

    uchi.Widget(random_structure, vc)
    return


if __name__ == "__main__":
    app.run()
