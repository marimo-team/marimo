# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters

HAS_DEPS = DependencyManager.flax.has()


def _names_in_order(html: str) -> list[str]:
    """Child names as rendered, top-to-bottom."""
    return re.findall(r'nn-t-name">([^<]+)</span>', html)


@pytest.mark.skipif(not HAS_DEPS, reason="flax not installed")
class TestFlaxFormatter:
    def test_format_simple_module(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        model = nnx.Linear(10, 5, rngs=nnx.Rngs(0))
        html = format(model).text

        assert "nn-t" in html
        assert "Linear" in html
        assert "nn-t-summary" in html

    def test_format_sequential(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        model = nnx.Sequential(
            nnx.Linear(784, 256, rngs=nnx.Rngs(0)),
            nnx.relu,
            nnx.Linear(256, 10, rngs=nnx.Rngs(1)),
        )
        html = format(model).text

        assert "Sequential" in html
        assert "Linear" in html
        # Tree structure elements
        assert "nn-t-node" in html
        assert "nn-t-arrow" in html
        # dtype/device in expand bodies of Linear layers
        assert "float32" in html
        assert "cpu" in html

    def test_format_nested_module(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        class SimpleNet(nnx.Module):
            def __init__(self, rngs: nnx.Rngs) -> None:
                self.features = nnx.Sequential(
                    nnx.Conv(3, 16, kernel_size=(3, 3), rngs=rngs),
                )
                self.classifier = nnx.Linear(16, 10, rngs=rngs)

        html = format(SimpleNet(nnx.Rngs(0))).text

        assert "SimpleNet" in html
        assert "features" in html
        assert "classifier" in html
        assert "Conv" in html

    def test_children_in_definition_order(self) -> None:
        """Children render in __init__ order, not alphabetical.

        `nnx.iter_children` sorts by name; the formatter must instead
        preserve definition order to match the model's actual structure.
        """
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        class Model(nnx.Module):
            def __init__(self, rngs: nnx.Rngs) -> None:
                self.linear = nnx.Linear(4, 8, rngs=rngs)
                self.bn = nnx.BatchNorm(8, rngs=rngs)
                self.dropout = nnx.Dropout(0.2, rngs=rngs)
                self.linear_out = nnx.Linear(8, 2, rngs=rngs)

        html = format(Model(nnx.Rngs(0))).text
        assert _names_in_order(html) == [
            "linear",
            "bn",
            "dropout",
            "linear_out",
        ]

    def test_non_trainable_state_not_shown(self) -> None:
        """Only trainable params are counted, matching PyTorch buffers.

        BatchNorm running statistics and a Dropout's PRNG state must not
        appear in the output, so the count stays consistent with the
        PyTorch formatter (which ignores buffers).
        """
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        class Model(nnx.Module):
            def __init__(self, rngs: nnx.Rngs) -> None:
                self.bn = nnx.BatchNorm(16, rngs=rngs)
                self.dropout = nnx.Dropout(0.2, rngs=rngs)

        html = format(Model(nnx.Rngs(0))).text
        assert "state" not in html
        # Trainable params (BatchNorm scale + bias = 32) are still shown.
        assert "params" in html

    def test_category_badges(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        class Model(nnx.Module):
            def __init__(self, rngs: nnx.Rngs) -> None:
                self.linear = nnx.Linear(8, 8, rngs=rngs)  # weight
                self.act = nnx.PReLU()  # activation
                self.norm = nnx.BatchNorm(8, rngs=rngs)  # normalization
                self.drop = nnx.Dropout(0.5, rngs=rngs)  # regularization

        html = format(Model(nnx.Rngs(0))).text

        # Assert on the layer type-pills specifically -- the footer legend
        # always contains a swatch for every category, so a bare
        # `data-cat="..."` check would pass even without categorized layers.
        for cat in ("weight", "act", "norm", "reg"):
            assert f'class="nn-t-type" data-cat="{cat}"' in html

    def test_legend_present(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format

        html = format(nnx.Linear(10, 5, rngs=nnx.Rngs(0))).text

        assert "nn-t-legend" in html
        assert "Module types" in html

    def test_returns_html_type(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import format
        from marimo._output.hypertext import Html

        result = format(nnx.Linear(10, 5, rngs=nnx.Rngs(0)))
        assert isinstance(result, Html)

    def test_layer_category(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import _layer_category

        r = nnx.Rngs(0)
        assert _layer_category(nnx.Linear(1, 1, rngs=r)) == "weight"
        assert (
            _layer_category(nnx.Conv(1, 1, kernel_size=(1,), rngs=r))
            == "weight"
        )
        assert _layer_category(nnx.Embed(2, 2, rngs=r)) == "weight"
        assert (
            _layer_category(nnx.LoRALinear(2, 2, lora_rank=1, rngs=r))
            == "weight"
        )
        assert _layer_category(nnx.PReLU()) == "act"
        assert _layer_category(nnx.BatchNorm(1, rngs=r)) == "norm"
        assert _layer_category(nnx.LayerNorm(1, rngs=r)) == "norm"
        assert _layer_category(nnx.Dropout(0.5, rngs=r)) == "reg"
        # Container has no category
        assert _layer_category(nnx.Sequential()) is None

    def test_counts_params_only(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import _counts

        # Linear(4, 8): kernel 4*8 + bias 8 = 40 params.
        param_count, param_bytes = _counts(nnx.Linear(4, 8, rngs=nnx.Rngs(0)))
        assert param_count == 40
        assert param_bytes == 40 * 4  # float32

    def test_counts_ignores_non_trainable_state(self) -> None:
        """Only trainable params count; buffers/state are not included."""
        from flax import nnx

        from marimo._output.formatters.flax_formatters import _counts

        # BatchNorm(8): scale + bias = 16 params; the 16 running-stat
        # elements (BatchStat) are not counted.
        param_count, _ = _counts(nnx.BatchNorm(8, rngs=nnx.Rngs(0)))
        assert param_count == 16

        # Dropout has no trainable params (only PRNG state) -> 0.
        assert _counts(nnx.Dropout(0.2, rngs=nnx.Rngs(0))) == (0, 0)

    def test_config_kwargs(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import _config_kwargs

        kwargs = _config_kwargs(nnx.Linear(10, 5, rngs=nnx.Rngs(0)))
        assert "in_features" in kwargs
        assert "out_features" in kwargs

    def test_child_modules_order(self) -> None:
        from flax import nnx

        from marimo._output.formatters.flax_formatters import _child_modules

        class Model(nnx.Module):
            def __init__(self, rngs: nnx.Rngs) -> None:
                self.first = nnx.Linear(2, 2, rngs=rngs)
                self.second = nnx.BatchNorm(2, rngs=rngs)
                self.third = nnx.Linear(2, 2, rngs=rngs)

        names = [name for name, _ in _child_modules(Model(nnx.Rngs(0)))]
        assert names == ["first", "second", "third"]

    def test_collect_dtype_device(self) -> None:
        import jax.numpy as jnp

        from marimo._output.formatters.flax_formatters import (
            _collect_dtype_device,
        )

        dtype_str, device_str = _collect_dtype_device(
            [jnp.zeros(2), jnp.ones(3)]
        )
        assert dtype_str == "float32"
        assert "cpu" in device_str

        # Mixed dtypes are joined with "/".
        dtype_str, _ = _collect_dtype_device(
            [
                jnp.zeros(2, dtype=jnp.float32),
                jnp.zeros(2, dtype=jnp.float16),
            ]
        )
        assert dtype_str == "float16/float32"

        # Empty -> en-dash placeholders.
        assert _collect_dtype_device([]) == ("–", "–")

    def test_fmt_integer(self) -> None:
        from marimo._output.formatters._nn_tree import _fmt_integer

        assert _fmt_integer(500) == "500"
        assert _fmt_integer(1_500) == "1.5K"
        assert _fmt_integer(1_500_000) == "1.5M"

    def test_formatter_registration(self) -> None:
        """Smoke test: the formatter registers and produces output."""
        register_formatters()

        from flax import nnx

        from marimo._output.formatting import get_formatter

        model = nnx.Linear(10, 5, rngs=nnx.Rngs(0))
        formatter = get_formatter(model)
        assert formatter is not None
        mimetype, data = formatter(model)
        assert mimetype == "text/html"
        assert "nn-t" in data
        assert "Linear" in data
