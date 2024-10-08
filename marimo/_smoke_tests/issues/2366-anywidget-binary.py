import marimo

__generated_with = "0.8.17"
app = marimo.App()


@app.cell
def __():
    import anywidget
    import traitlets



    class Widget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
          let arr = model.get("arr");
          el.innerText = arr.bytes instanceof DataView;
        }
        export default { render };
        """
        arr = traitlets.Dict().tag(sync=True)

    import numpy as np
    arr = np.array([1, 2, 3])
    Widget(
        arr={
            "bytes": arr.tobytes(),
            "shape": arr.shape,
            "dtype": str(arr.dtype),
        }
    )
    return Widget, anywidget, arr, np, traitlets


if __name__ == "__main__":
    app.run()
