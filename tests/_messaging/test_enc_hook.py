# Copyright 2026 Marimo. All rights reserved.

import decimal
import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import enc_hook, getcallable


def test_getcallable() -> None:
    """Test the getcallable utility function."""

    class WithCallable:
        def my_method(self) -> str:
            return "called"

    class WithNonCallable:
        my_method = "not callable"

    class WithGetattr:
        def __getattr__(self, name: str) -> str:
            return f"attr_{name}"

    # Returns callable when attribute exists and is callable
    obj_callable = WithCallable()
    result = getcallable(obj_callable, "my_method")
    assert result is not None
    assert callable(result)
    assert result() == "called"

    # Returns None when attribute exists but is not callable
    obj_non_callable = WithNonCallable()
    result = getcallable(obj_non_callable, "my_method")
    assert result is None

    # Returns None when attribute doesn't exist
    result = getcallable(obj_callable, "nonexistent")
    assert result is None

    # Returns None for objects with __getattr__ returning non-callable
    obj_getattr = WithGetattr()
    assert hasattr(obj_getattr, "any_attr")  # hasattr returns True
    result = getcallable(obj_getattr, "any_attr")
    assert result is None


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


def test_object_with_getattr_returning_non_callable() -> None:
    """Test that objects implementing __getattr__ don't break serialization.

    Some libraries (like rdflib.Namespace) implement __getattr__ to return
    non-callable objects for any attribute name. This caused hasattr() to
    return True for _marimo_serialize_ and _mime_, but calling them failed.

    See: https://github.com/marimo-team/marimo/issues/8096
    """

    class NamespaceLike:
        """Mimics rdflib.Namespace behavior."""

        def __init__(self, base: str):
            self.base = base

        def __getattr__(self, name: str) -> str:
            # Returns a string (non-callable) for any attribute
            return f"{self.base}{name}"

    ns = NamespaceLike("http://example.com/")

    # Verify that hasattr returns True for special methods
    assert hasattr(ns, "_marimo_serialize_")
    assert hasattr(ns, "_mime_")

    # But the attributes are not callable
    assert not callable(ns._marimo_serialize_)
    assert not callable(ns._mime_)

    # enc_hook should handle this gracefully without raising TypeError
    result = enc_hook(ns)

    # Should fall through to __dict__ handling
    assert isinstance(result, dict)
    assert result["base"] == "http://example.com/"


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
