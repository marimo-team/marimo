# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import html
import re
import typing

from marimo._output.formatters._nn_tree import (
    _CSS,
    ModuleCategory,
    _comma_to_br,
    _fmt_integer,
    _footer_html,
    _frozen_attr,
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


def _walk(mod: torch.nn.Module, name: str = "") -> str:
    """Recursively build HTML tree for an nn.Module (non-root nodes)."""
    children = list(mod.named_children())
    type_name = mod.__class__.__name__
    extra = _extra_repr_html(mod)
    cat = _layer_category(mod)

    name_html = f'<span class="nn-t-name">{name}</span> ' if name else ""
    cat_attr = f' data-cat="{cat}"' if cat is not None else ""
    type_span = f'<span class="nn-t-type"{cat_attr}>{type_name}</span>'
    pos_args = (
        f' <span class="nn-t-pos">{extra.positional}</span>'
        if extra.positional
        else ""
    )

    if not children:
        own_params = list(mod.parameters(recurse=False))
        num_params = sum(p.numel() for p in own_params)
        num_trainable = sum(p.numel() for p in own_params if p.requires_grad)
        info = _trainable_info(num_params, num_trainable)
        frozen = _frozen_attr(info.is_frozen or num_params == 0)

        params = (
            f'<span class="nn-t-params"{frozen}>'
            f"{_fmt_integer(num_params)}{info.note}</span>"
            if num_params > 0
            else ""
        )

        # Build expand body: kwargs first, then dtype/device
        body_parts: list[str] = []
        if extra.kwargs:
            body_parts.append(_comma_to_br(extra.kwargs))
        if own_params:
            dtype_s, device_s = _collect_dtype_device(own_params)
            if body_parts:
                body_parts.append(
                    '<div class="nn-t-expand-sep">'
                    '<span class="nn-t-expand-sep-label">tensor</span>'
                    "</div>"
                )
            body_parts.append(
                f'<span class="nn-t-key">dtype</span> {dtype_s}'
                f"<br>"
                f'<span class="nn-t-key">device</span> {device_s}'
            )

        if body_parts:
            kw_inline = (
                f' <span class="nn-t-args">{extra.kwargs}</span>'
                if extra.kwargs
                else ""
            )
            return (
                f'<details class="nn-t-expand"{frozen}>'
                f"<summary>"
                f'<span class="nn-t-spacer"></span>'
                f"{name_html}{type_span}{pos_args}{kw_inline}"
                f"{params}"
                f"</summary>"
                f'<div class="nn-t-expand-body">{"".join(body_parts)}</div>'
                f"</details>"
            )
        return (
            f'<div class="nn-t-leaf"{frozen}>'
            f'<span class="nn-t-spacer"></span>'
            f"{name_html}{type_span}{pos_args}"
            f"{params}"
            f"</div>"
        )

    # Container node: aggregate all descendant parameters
    all_sub = list(mod.parameters())
    total_sub = sum(p.numel() for p in all_sub)
    total_trainable = sum(p.numel() for p in all_sub if p.requires_grad)
    info = _trainable_info(total_sub, total_trainable)

    total_params = (
        f'<span class="nn-t-params">'
        f"{_fmt_integer(total_sub)}{info.note}</span>"
    )

    children_html = "\n".join(
        _walk(child_mod, child_name) for child_name, child_mod in children
    )

    return (
        f'<details class="nn-t-node"{_frozen_attr(info.is_frozen)}>'
        f"<summary>"
        f'<span class="nn-t-arrow">&#9654;</span>'
        f"{name_html}{type_span}"
        f"{total_params}"
        f"</summary>"
        f'<div class="nn-t-children">{children_html}</div>'
        f"</details>"
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
    children = list(module.named_children())

    total_params = sum(p.numel() for p in all_params)
    trainable_params = sum(p.numel() for p in all_params if p.requires_grad)
    size_bytes = sum(p.numel() * p.element_size() for p in all_params)
    size_mb = size_bytes / (1024 * 1024)

    trainable_note = (
        f" ({_fmt_integer(trainable_params)} trainable)"
        if trainable_params != total_params
        else ""
    )
    header = (
        f'<div class="nn-t-header">'
        f'<span class="nn-t-root">{module.__class__.__name__}</span>'
        f'<span class="nn-t-summary">'
        f"{_fmt_integer(total_params)} params{trainable_note}"
        f" \u00b7 {size_mb:.1f} MB"
        f"</span>"
        f"</div>"
    )

    if children:
        body_html = "\n".join(
            _walk(child_mod, child_name) for child_name, child_mod in children
        )
        body = f'<div class="nn-t-body">{body_html}</div>'
    else:
        extra = _extra_repr_html(module)
        combined = ", ".join(
            part for part in (extra.positional, extra.kwargs) if part
        )
        extra_html = (
            f'<span class="nn-t-args">{combined}</span>' if combined else ""
        )
        body = (
            f'<div class="nn-t-body">'
            f'<div class="nn-t-leaf">{extra_html}</div>'
            f"</div>"
        )

    divider = '<div class="nn-t-divider"></div>'
    footer = _footer_html()

    html = (
        f'<div class="nn-t"><style>{_CSS}</style>'
        f"{header}{divider}{body}{footer}"
        f"</div>"
    )
    return Html(html)


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
