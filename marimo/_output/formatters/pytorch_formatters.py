# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import html
import re
import typing

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.hypertext import Html

if typing.TYPE_CHECKING:
    import torch  # type: ignore[import-not-found]

ModuleCategory = typing.Literal["weight", "act", "norm", "reg"]

_LABELS: dict[ModuleCategory, str] = {
    "weight": "Weight",
    "act": "Activation",
    "norm": "Normalization",
    "reg": "Regularization",
}

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

# Matches a comma followed by a space that is NOT inside parentheses.
_TOP_COMMA_RE = re.compile(r",\s+(?![^()]*\))")


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


def _comma_to_br(html_str: str) -> str:
    """Replace top-level comma separators with <br> for multi-line display."""
    return _TOP_COMMA_RE.sub("<br>", html_str)


def _frozen_attr(is_frozen: bool) -> str:
    """Build the HTML data-frozen attribute string when needed."""
    if is_frozen:
        return ' data-frozen="true"'
    return ""


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


def _extra_repr_html(module: torch.nn.Module) -> ExtraRepr:
    """Build HTML from a module's extra_repr().

    Uses PyTorch's own extra_repr() hook -- every built-in layer already
    implements this, and custom modules can override it too.  We highlight
    the ``key=`` portions of ``key=value`` pairs; positional arguments and
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


def _fmt_integer(n: int) -> str:
    """Format int into a human readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


_CSS = """\
.nn-t {
  font-size: 0.8125rem;
  line-height: 1.5;
  background-color: var(--slate-1);
  color: var(--slate-12);
  border-radius: 6px;
}

/* Header */
.nn-t-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.75rem 0.5rem 0.75rem;
}
.nn-t-root {
  font-family: monospace;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--slate-12);
}
.nn-t-summary {
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--slate-11);
  margin-left: auto;
}
.nn-t-divider {
  height: 1px;
  background-color: var(--slate-3);
  margin: 0 0.75rem;
}

/* Body */
.nn-t-body {
  padding: 0.5rem 0 0.5rem 0.75rem;
}

/* Shared row layout */
.nn-t-leaf,
.nn-t-node > summary,
.nn-t-expand > summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.1875rem 0.75rem 0.1875rem 0;
  white-space: nowrap;
}
.nn-t-leaf:hover,
.nn-t-node > summary:hover,
.nn-t-expand > summary:hover {
  background: var(--slate-2);
}

/* Expandable nodes */
.nn-t-node {
  margin: 0;
  padding: 0;
}
.nn-t-node > summary {
  cursor: pointer;
  list-style: none;
}
.nn-t-node > summary::-webkit-details-marker {
  display: none;
}

/* Disclosure arrow */
.nn-t-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  flex-shrink: 0;
  color: var(--slate-9);
  transition: transform 0.12s;
  font-size: 0.5rem;
}
.nn-t-node[open] > summary .nn-t-arrow {
  transform: rotate(90deg);
}

/* Leaf spacer matches arrow width */
.nn-t-spacer {
  display: inline-block;
  width: 1rem;
  flex-shrink: 0;
}

/* Children with indent guide */
.nn-t-children {
  margin-left: calc(0.5rem - 1px);
  padding-left: 0.75rem;
  border-left: 1px solid var(--slate-3);
}

/* Text elements */
.nn-t-name {
  font-family: monospace;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--slate-12);
}
.nn-t-type {
  font-family: monospace;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--slate-12);
  padding: 0.0625rem 0.375rem;
  border-radius: 0.1875rem;
  background: var(--slate-3);
}
.nn-t-type[data-cat="weight"] { --pill-bg: var(--blue-3); --pill-fg: var(--blue-11); }
.nn-t-type[data-cat="norm"]   { --pill-bg: var(--green-3); --pill-fg: var(--green-11); }
.nn-t-type[data-cat="act"]    { --pill-bg: var(--orange-3); --pill-fg: var(--orange-11); }
.nn-t-type[data-cat="reg"]    { --pill-bg: var(--crimson-3); --pill-fg: var(--crimson-11); }
.nn-t-type[data-cat] {
  background: var(--pill-bg);
  color: var(--pill-fg);
}
/* Positional args (always visible, never truncated) */
.nn-t-pos {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  flex-shrink: 0;
}

/* Keyword args (truncated with ellipsis) */
.nn-t-args {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* Expandable args */
.nn-t-expand {
  margin: 0;
  padding: 0;
}
.nn-t-expand > summary {
  cursor: pointer;
  list-style: none;
}
.nn-t-expand > summary::-webkit-details-marker {
  display: none;
}
.nn-t-expand > summary .nn-t-mini-arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  flex-shrink: 0;
  color: var(--slate-8);
  font-size: 0.35rem;
  transition: transform 0.12s;
}
.nn-t-expand[open] > summary .nn-t-mini-arrow {
  transform: rotate(90deg);
}
.nn-t-expand[open] > summary .nn-t-args {
  display: none;
}
.nn-t-expand-body {
  font-family: monospace;
  font-size: 0.8125rem;
  color: var(--slate-11);
  padding: 0.125rem 0.75rem 0.25rem 2.75rem;
  line-height: 1.6;
}
.nn-t-key {
  color: var(--slate-9);
}

/* Param count */
.nn-t-params {
  color: var(--slate-10);
  font-family: monospace;
  font-size: 0.75rem;
  margin-left: auto;
  padding-left: 1rem;
  flex-shrink: 0;
}
[data-frozen] > .nn-t-type,
[data-frozen] > .nn-t-pos,
[data-frozen] > .nn-t-args,
[data-frozen] > .nn-t-params,
[data-frozen] > .nn-t-spacer,
[data-frozen] > .nn-t-mini-arrow,
[data-frozen] > summary > .nn-t-type,
[data-frozen] > summary > .nn-t-pos,
[data-frozen] > summary > .nn-t-args,
[data-frozen] > summary > .nn-t-params,
[data-frozen] > summary > .nn-t-arrow {
  opacity: 0.55;
}

/* Footer with info-hover legend */
.nn-t-footer {
  display: flex;
  justify-content: flex-end;
  padding: 0.25rem 0.75rem 0.375rem 0.75rem;
}
.nn-t-info {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--slate-8);
  cursor: default;
}
.nn-t-info:hover { color: var(--slate-10); }
.nn-t-info:hover .nn-t-legend {
  visibility: visible;
  opacity: 1;
}
.nn-t-info svg {
  width: 0.875rem;
  height: 0.875rem;
}
.nn-t-legend {
  visibility: hidden;
  opacity: 0;
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  z-index: 10;
  max-height: 12rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.375rem 0.625rem;
  background: var(--slate-1);
  border: 1px solid var(--slate-3);
  border-radius: 6px;
  white-space: nowrap;
  transition: opacity 0.12s, visibility 0.12s;
  font-family: monospace;
  font-size: 0.75rem;
  color: var(--slate-11);
}
.nn-t-legend-title {
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--slate-9);
  margin-bottom: 0.0625rem;
}
.nn-t-legend-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
.nn-t-swatch {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.875rem;
  height: 0.8125rem;
  border-radius: 0.1875rem;
  flex-shrink: 0;
  background: var(--slate-3);
}
.nn-t-swatch[data-cat="weight"] { background: var(--blue-3); }
.nn-t-swatch[data-cat="norm"]   { background: var(--green-3); }
.nn-t-swatch[data-cat="act"]    { background: var(--orange-3); }
.nn-t-swatch[data-cat="reg"]    { background: var(--crimson-3); }
.nn-t-swatch-dot {
  width: 0.25rem;
  height: 0.25rem;
  border-radius: 50%;
  background: var(--slate-8);
}
.nn-t-swatch[data-cat="weight"] .nn-t-swatch-dot { background: var(--blue-11); }
.nn-t-swatch[data-cat="norm"] .nn-t-swatch-dot   { background: var(--green-11); }
.nn-t-swatch[data-cat="act"] .nn-t-swatch-dot    { background: var(--orange-11); }
.nn-t-swatch[data-cat="reg"] .nn-t-swatch-dot    { background: var(--crimson-11); }
.nn-t-swatch[data-dim] { opacity: 0.55; }
.nn-t-legend-sep {
  height: 1px;
  background: var(--slate-3);
  margin: 0.125rem 0;
}"""


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

        if extra.kwargs:
            kw_inline = f' <span class="nn-t-args">{extra.kwargs}</span>'
            kw_expanded = _comma_to_br(extra.kwargs)
            return (
                f'<details class="nn-t-expand"{frozen}>'
                f"<summary>"
                f'<span class="nn-t-mini-arrow">&#9654;</span>'
                f"{name_html}{type_span}{pos_args}{kw_inline}"
                f"{params}"
                f"</summary>"
                f'<div class="nn-t-expand-body">{kw_expanded}</div>'
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
        module: A ``torch.nn.Module`` instance.

    Returns:
        A ``marimo.Html`` object with the rendered tree.
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

    legend_title = '<span class="nn-t-legend-title">Module types</span>'
    legend_items = "".join(
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch" data-cat="{cat}">'
        f'<span class="nn-t-swatch-dot"></span></span>{label}'
        f"</span>"
        for cat, label in _LABELS.items()
    )
    # Lucide "info" icon (ISC license)
    info_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 16v-4"/>'
        '<path d="M12 8h.01"/>'
        "</svg>"
    )
    footer = (
        f'<div class="nn-t-footer">'
        f'<span class="nn-t-info">{info_svg}'
        f'<span class="nn-t-legend">{legend_title}{legend_items}'
        f'<span class="nn-t-legend-sep"></span>'
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch"><span class="nn-t-swatch-dot"></span></span>'
        f"Trainable</span>"
        f'<span class="nn-t-legend-item">'
        f'<span class="nn-t-swatch" data-dim><span class="nn-t-swatch-dot"></span></span>'
        f"Frozen / no params</span>"
        f"</span>"
        f"</span>"
        f"</div>"
    )

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
        import torch.nn  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: E501

        from marimo._output import formatting
        from marimo._output.formatters.pytorch_formatters import format as fmt
        from marimo._messaging.mimetypes import KnownMimeType

        @formatting.formatter(torch.nn.Module)
        def _format_module(
            module: torch.nn.Module,
        ) -> tuple[KnownMimeType, str]:
            return ("text/html", fmt(module).text)
