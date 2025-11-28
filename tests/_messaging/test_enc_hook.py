# Copyright 2025 Marimo. All rights reserved.

import decimal
import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import enc_hook


def test_enc_hook() -> None:
    """Test the enc_hook function."""
    assert enc_hook(1) == 1
    assert enc_hook("hello") == "hello"
    assert enc_hook(3.14) == 3.14
    assert enc_hook(True) is True
    assert enc_hook(None) is None

    if DependencyManager.numpy.imported():
        import numpy as np

        assert enc_hook(np.array([1, 2, 3])) == [1, 2, 3]
        assert enc_hook(np.array([1, 2, 3])) == [1, 2, 3]


@pytest.mark.skipif(
    not DependencyManager.pillow.imported(),
    reason="Pillow not installed",
)
def test_serialize_pillow_image() -> None:
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="red")

    result = enc_hook(img)

    assert result is not None
    assert result.startswith("data:image/png;base64,")


@pytest.mark.skipif(
    not DependencyManager.matplotlib.imported(),
    reason="Matplotlib not installed",
)
def test_serialize_matplotlib_figure() -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])

    # Serialize the figure
    result = enc_hook(fig)
    for obj in [fig, ax]:
        result = enc_hook(obj)
        assert isinstance(result, dict)

        assert "mimetype" in result
        assert "data" in result

        assert "application/vnd.marimo+mimebundle" in result["mimetype"]
        assert "image/png" in result["data"]

        image_data = json.loads(result["data"])
        assert "image/png" in image_data
        assert image_data["image/png"].startswith("data:image/png;base64,")


def test_serialize_decimal() -> None:
    decimal_obj = decimal.Decimal("123.45")
    result = enc_hook(decimal_obj)
    assert result == "123.45"

    # Nans, infinities, and -0
    decimal_obj = decimal.Decimal("NaN")
    result = enc_hook(decimal_obj)
    assert result == "NaN"
    decimal_obj = decimal.Decimal("Infinity")
    result = enc_hook(decimal_obj)
    assert result == "Infinity"
    decimal_obj = decimal.Decimal("-0")
    result = enc_hook(decimal_obj)
    assert result == "-0"
