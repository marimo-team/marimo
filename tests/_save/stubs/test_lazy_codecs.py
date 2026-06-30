# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from marimo._save.loaders.lazy import maybe_update_lazy_stub  # noqa: E402
from marimo._save.stubs.lazy_stub import (  # noqa: E402
    BLOB_DESERIALIZERS,
    BLOB_SERIALIZERS,
)


def test_tensor_resolves_to_pt_codec() -> None:
    assert maybe_update_lazy_stub(torch.ones(4)) == "pt"


def test_parameter_resolves_to_pt_codec_via_mro() -> None:
    param = torch.nn.Parameter(torch.ones(4))
    assert maybe_update_lazy_stub(param) == "pt"


def test_pt_round_trip() -> None:
    tensor = torch.randn(8, 3)
    data = BLOB_SERIALIZERS["pt"](tensor)
    restored = BLOB_DESERIALIZERS[".pt"](data, "torch.Tensor")
    assert torch.equal(tensor, restored)
    assert restored.dtype == tensor.dtype


def test_pt_round_trip_preserves_parameter_subclass() -> None:
    param = torch.nn.Parameter(torch.randn(4))
    data = BLOB_SERIALIZERS["pt"](param)
    restored = BLOB_DESERIALIZERS[".pt"](data, "torch.nn.parameter.Parameter")
    assert isinstance(restored, torch.nn.Parameter)
    assert torch.equal(param.data, restored.data)
