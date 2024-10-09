import marimo

__generated_with = "0.9.1"
app = marimo.App(width="medium")


@app.cell
def __():
    # binary data is a png image of a small purple square
    CONTENT = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x14\x00\x00\x00\x14\x08\x02\x00\x00\x00\x02\xeb\x8aZ\x00\x00\x00\tpHYs\x00\x00.#\x00\x00.#\x01x\xa5?v\x00\x00\x00\x1dIDAT8\xcbc\xac\x11\xa9g \x1701P\x00F5\x8fj\x1e\xd5<\xaa\x99r\xcd\x00m\xba\x017\xd3\x00\xdf\xcb\x00\x00\x00\x00IEND\xaeB`\x82'
    return (CONTENT,)


@app.cell
def __(CONTENT):
    import anywidget
    import traitlets

    class BytesWidget(anywidget.AnyWidget):
        _esm = """
        function render({ model, el }) {
            let value = model.get("value");
            const isDataView = document.createElement("div");
            isDataView.innerText = `Is  DataView: ${value instanceof DataView}`;
            el.appendChild(isDataView);

            const image = document.createElement("img");
            image.src = URL.createObjectURL(new Blob([value]));
            el.appendChild(image);
        }
        export default { render };
        """
        value = traitlets.Bytes().tag(sync=True)

    # binary data is a png image of a small purple square
    BytesWidget(value=CONTENT)
    return BytesWidget, anywidget, traitlets


@app.cell
def __(CONTENT, mo):
    # Not lossy
    mo.image(CONTENT.decode("latin1").encode("latin1"))
    return


@app.cell
def __(CONTENT, mo):
    # Is lossy
    mo.image(CONTENT.decode("utf-8", errors="replace").encode("utf-8"))
    return


@app.cell
def __():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
