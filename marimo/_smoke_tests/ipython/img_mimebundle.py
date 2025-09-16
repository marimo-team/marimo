import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from io import BytesIO
    from PIL import Image, ImageDraw


    class BlueOnGray:
        def __init__(self, text, retina=False):
            self.text = text
            self.retina = retina

        def _repr_mimebundle_(self, include=None, exclude=None):
            w, h = 200, 80
            f = 2 if self.retina else 1
            img = Image.new("RGB", (w, h), color="lightgray")
            metadata = {"image/png": {"width": w // f, "height": h // f}}
            draw = ImageDraw.Draw(img)
            draw.text((10, 30), self.text, fill="blue")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return {
                "image/png": buffer.getvalue(),
                "text/html": f"<span style='color: blue; background-color: gray'>{self.text}</span>",
            }, metadata


    BlueOnGray("Blue text on gray background")
    return


if __name__ == "__main__":
    app.run()
