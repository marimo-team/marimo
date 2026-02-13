# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters

HAS_DEPS = DependencyManager.torch.has()


@pytest.mark.skipif(not HAS_DEPS, reason="torch not installed")
class TestPyTorchFormatter:
    def test_format_simple_module(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        model = nn.Linear(10, 5)
        result = format(model)
        html = result.text

        assert "nn-t" in html
        assert "Linear" in html
        # Should contain param count
        assert "nn-t-summary" in html

    def test_format_sequential(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        model = nn.Sequential(
            nn.Linear(784, 256),
            nn.ReLU(),
            nn.Linear(256, 10),
        )
        result = format(model)
        html = result.text

        assert "Sequential" in html
        assert "Linear" in html
        assert "ReLU" in html
        # Tree structure elements
        assert "nn-t-node" in html
        assert "nn-t-arrow" in html

    def test_format_nested_module(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        class SimpleNet(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.features = nn.Sequential(
                    nn.Conv2d(3, 16, 3),
                    nn.ReLU(),
                )
                self.classifier = nn.Linear(16, 10)

        model = SimpleNet()
        result = format(model)
        html = result.text

        assert "SimpleNet" in html
        assert "features" in html
        assert "classifier" in html
        assert "Conv2d" in html

    def test_format_frozen_model(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 2),
        )
        for p in model.parameters():
            p.requires_grad = False

        result = format(model)
        html = result.text

        assert "frozen" in html.lower()
        assert "data-frozen" in html

    def test_format_partially_frozen(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        class PartiallyFrozen(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.backbone = nn.Linear(10, 5)
                self.head = nn.Linear(5, 2)
                for p in self.backbone.parameters():
                    p.requires_grad = False

        model = PartiallyFrozen()
        result = format(model)
        html = result.text

        assert "trainable" in html.lower()

    def test_category_badges(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        model = nn.Sequential(
            nn.Linear(10, 5),  # weight
            nn.ReLU(),  # activation
            nn.BatchNorm1d(5),  # normalization
            nn.Dropout(0.5),  # regularization
        )
        result = format(model)
        html = result.text

        assert 'data-cat="weight"' in html
        assert 'data-cat="act"' in html
        assert 'data-cat="norm"' in html
        assert 'data-cat="reg"' in html

    def test_legend_present(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format

        model = nn.Linear(10, 5)
        result = format(model)
        html = result.text

        assert "nn-t-legend" in html
        assert "Module types" in html
        assert "Trainable" in html
        assert "Frozen" in html

    def test_param_count_formatting(self) -> None:
        from marimo._output.formatters.pytorch_formatters import _fmt_integer

        assert _fmt_integer(500) == "500"
        assert _fmt_integer(1_500) == "1.5K"
        assert _fmt_integer(1_500_000) == "1.5M"

    def test_extra_repr_html(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import (
            _extra_repr_html,
        )

        # Linear uses all kwargs: in_features=10, out_features=5, bias=True
        linear = nn.Linear(10, 5)
        extra = _extra_repr_html(linear)
        assert extra.positional == ""
        assert "in_features" in extra.kwargs

        # Conv2d has positional args: 3, 16, then kwargs
        conv = nn.Conv2d(3, 16, kernel_size=3)
        extra = _extra_repr_html(conv)
        assert extra.positional == "3, 16"
        assert "kernel_size" in extra.kwargs

    def test_layer_category(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import (
            _layer_category,
        )

        assert _layer_category(nn.Linear(1, 1)) == "weight"
        assert _layer_category(nn.ReLU()) == "act"
        assert _layer_category(nn.BatchNorm1d(1)) == "norm"
        assert _layer_category(nn.Dropout()) == "reg"
        # Container has no category
        assert _layer_category(nn.Sequential()) is None

    def test_trainable_info(self) -> None:
        from marimo._output.formatters.pytorch_formatters import (
            _trainable_info,
        )

        # All trainable
        info = _trainable_info(100, 100)
        assert info.note == ""
        assert info.is_frozen is False

        # All frozen
        info = _trainable_info(100, 0)
        assert "frozen" in info.note
        assert info.is_frozen is True

        # Partially frozen
        info = _trainable_info(100, 50)
        assert "trainable" in info.note
        assert info.is_frozen is False

    def test_returns_html_type(self) -> None:
        import torch.nn as nn

        from marimo._output.formatters.pytorch_formatters import format
        from marimo._output.hypertext import Html

        model = nn.Linear(10, 5)
        result = format(model)
        assert isinstance(result, Html)

    def test_formatter_registration(self) -> None:
        """Smoke test: the formatter registers and produces output."""
        register_formatters()

        import torch.nn as nn

        from marimo._output.formatting import get_formatter

        model = nn.Linear(10, 5)
        formatter = get_formatter(model)
        assert formatter is not None
        mimetype, data = formatter(model)
        assert mimetype == "text/html"
        assert "nn-t" in data
        assert "Linear" in data
