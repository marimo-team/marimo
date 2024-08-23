import base64
import io

import marimo as mo
from PIL import Image


def _pillow_image_to_base64_string(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def image(path: str) -> str:
    img = Image.open(path)
    data_url = "data:image/png;base64," + _pillow_image_to_base64_string(img)
    return mo.image(src=data_url)
