# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import html
import re
import typing

from marimo._output.formatters._nn_tree import (
    LeafBody,
    ModuleCategory,
    TreeNode,
    _comma_to_br,
    _fmt_integer,
    render_model,
)
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.hypertext import Html

if typing.TYPE_CHECKING:
    import torch  # type: ignore[import-not-found]

# Map torch.nn.modules.<subpackage> to our display category.
#
# PyTorch organises its layers into subpackages by purpose
# (e.g. torch.nn.modules.conv, torch.nn.modules.activation), so we
# can derive the category from `type(module).__module__` without
# enumerating every class.
#
# Caveat: MultiheadAttention lives in activation.py for historical
# reasons, so it gets "act" here rather than "weight".  Correcting
# that would require a per-class override; for now the colour is
# acceptable since attention is arguably its own category anyway.
_MODULE_CATEGORY: dict[str, ModuleCategory] = {
    # Learnable / weighted layers
    "linear": "weight",
    "conv": "weight",
    "sparse": "weight",  # Embedding, EmbeddingBag
    "rnn": "weight",  # LSTM, GRU, RNN
    "transformer": "weight",
    # Activation functions (+ MultiheadAttention, see caveat above)
    "activation": "act",
    # Normalization
    "batchnorm": "norm",
    "normalization": "norm",  # LayerNorm, GroupNorm, RMSNorm
    "instancenorm": "norm",
    # Regularization
    "dropout": "reg",
}

# Matches "key=" at the start of a key=value token inside extra_repr().
_KEY_RE = re.compile(r"(?<![=\w])(\w+)=")


@dataclasses.dataclass
class ExtraRepr:
    """Parsed HTML fragments from a module's extra_repr() output."""

    positional: str
    kwargs: str


@dataclasses.dataclass
class TrainableInfo:
    """Summary of parameter trainability for display."""

    note: str
    is_frozen: bool


def _trainable_info(total: int, trainable: int) -> TrainableInfo:
    """Compute trainability note and frozen flag from parameter counts."""
    if total > 0 and trainable == 0:
        return TrainableInfo(note=" (frozen)", is_frozen=True)
    if total > 0 and trainable != total:
        return TrainableInfo(
            note=f" ({_fmt_integer(trainable)} trainable)",
            is_frozen=False,
        )
    return TrainableInfo(note="", is_frozen=False)


def _collect_dtype_device(
    params: typing.Iterable[torch.nn.Parameter],
) -> tuple[str, str]:
    """Summarise dtype and device across parameters.

    Returns `(dtype_str, device_str)`.  When all parameters agree the
    value is a single token (e.g. `"float32"`); when mixed the unique
    values are joined with `"/"` (e.g. `"float32/float16"`).
    If *params* is empty both strings are `"–"`.
    """
    dtypes: set[str] = set()
    devices: set[str] = set()
    for p in params:
        dtypes.add(str(p.dtype).removeprefix("torch."))
        devices.add(str(p.device))
    if not dtypes:
        return ("\u2013", "\u2013")
    return (
        "/".join(sorted(dtypes)),
        "/".join(sorted(devices)),
    )


def _extra_repr_html(module: torch.nn.Module) -> ExtraRepr:
    """Build HTML from a module's extra_repr().

    Uses PyTorch's own extra_repr() hook -- every built-in layer already
    implements this, and custom modules can override it too.  We highlight
    the `key=` portions of `key=value` pairs; positional arguments and
    values are preserved as-is.

    Returns an ExtraRepr with positional and keyword HTML fragments.
    """
    raw = module.extra_repr()
    if not raw:
        return ExtraRepr("", "")

    escaped = html.escape(raw)
    key_repl = r'<span class="nn-t-key">\1</span>='

    # Find where keyword args start in the raw string
    m = _KEY_RE.search(escaped)
    if m is None:
        return ExtraRepr(positional=escaped, kwargs="")

    pos = m.start()
    if pos == 0:
        return ExtraRepr(positional="", kwargs=_KEY_RE.sub(key_repl, escaped))

    # Split: positional part is before the first key=, strip trailing ", "
    positional = escaped[:pos].rstrip(", ")
    kwargs = _KEY_RE.sub(key_repl, escaped[pos:])
    return ExtraRepr(positional=positional, kwargs=kwargs)


def _layer_category(module: torch.nn.Module) -> ModuleCategory | None:
    """Classify a module for color-coding using its source subpackage."""
    mod_path = type(module).__module__ or ""
    if mod_path.startswith("torch.nn.modules."):
        submod = mod_path.rsplit(".", 1)[-1]
        return _MODULE_CATEGORY.get(submod)
    return None


def _node(mod: torch.nn.Module, name: str = "") -> TreeNode:
    """Build a `TreeNode` for an nn.Module (recursing into children)."""
    type_name = mod.__class__.__name__
    cat = _layer_category(mod)
    children = list(mod.named_children())

    if children:
        all_sub = list(mod.parameters())
        total = sum(p.numel() for p in all_sub)
        trainable = sum(p.numel() for p in all_sub if p.requires_grad)
        info = _trainable_info(total, trainable)
        return TreeNode(
            name=name,
            type_name=type_name,
            category=cat,
            params_note=f"{_fmt_integer(total)}{info.note}",
            is_frozen=info.is_frozen,
            children=[_node(c, n) for n, c in children],
        )

    # Leaf module.
    own = list(mod.parameters(recurse=False))
    num = sum(p.numel() for p in own)
    trainable = sum(p.numel() for p in own if p.requires_grad)
    info = _trainable_info(num, trainable)
    extra = _extra_repr_html(mod)

    body: LeafBody | None = None
    if extra.kwargs or own:
        dtype = device = None
        if own:
            dtype, device = _collect_dtype_device(own)
        body = LeafBody(
            kwargs_inline=extra.kwargs,
            kwargs_block=_comma_to_br(extra.kwargs) if extra.kwargs else "",
            dtype=dtype,
            device=device,
            array_label="tensor",
        )

    return TreeNode(
        name=name,
        type_name=type_name,
        category=cat,
        params_note=f"{_fmt_integer(num)}{info.note}" if num > 0 else "",
        # Dim frozen layers and params-less layers (e.g. activations).
        is_frozen=info.is_frozen or num == 0,
        positional=extra.positional,
        body=body,
    )


def format(module: torch.nn.Module) -> Html:  # noqa: A001
    """Render a PyTorch nn.Module as a collapsible tree.

    The output shows the model name and summary in a fixed header,
    with child modules rendered as an expandable tree below.

    Args:
        module: A `torch.nn.Module` instance.

    Returns:
        A `marimo.Html` object with the rendered tree.
    """
    all_params = list(module.parameters())
    total_params = sum(p.numel() for p in all_params)
    trainable_params = sum(p.numel() for p in all_params if p.requires_grad)
    size_bytes = sum(p.numel() * p.element_size() for p in all_params)
    size_mb = size_bytes / (1024 * 1024)

    trainable_note = (
        f" ({_fmt_integer(trainable_params)} trainable)"
        if trainable_params != total_params
        else ""
    )
    summary = (
        f"{_fmt_integer(total_params)} params{trainable_note}"
        f" \u00b7 {size_mb:.1f} MB"
    )

    children = list(module.named_children())
    leaf_fallback = ""
    if not children:
        extra = _extra_repr_html(module)
        leaf_fallback = ", ".join(
            part for part in (extra.positional, extra.kwargs) if part
        )

    return render_model(
        root_type=module.__class__.__name__,
        summary=summary,
        nodes=[_node(c, n) for n, c in children],
        leaf_fallback=leaf_fallback,
    )


class PyTorchFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "torch"

    def register(self) -> None:
        import torch.nn  # type: ignore[import-not-found,import-untyped,unused-ignore]

        from marimo._messaging.mimetypes import KnownMimeType
        from marimo._output import formatting
        from marimo._output.formatters.pytorch_formatters import format as fmt

        @formatting.formatter(torch.nn.Module)
        def _format_module(
            module: torch.nn.Module,
        ) -> tuple[KnownMimeType, str]:
            return ("text/html", fmt(module).text)
