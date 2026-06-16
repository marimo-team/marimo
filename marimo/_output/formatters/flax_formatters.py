# Copyright 2026 Marimo. All rights reserved.
"""Rich formatter for Flax NNX modules (`flax.nnx.Module`).

Renders an `nnx.Module` as the same collapsible tree as the PyTorch
formatter (shared presentation lives in `_nn_tree`). NNX is pythonically
close to PyTorch -- submodules are plain attributes -- but its parameter
model differs: variables are typed (`nnx.Param`, `nnx.BatchStat`, ...) and
there is no per-parameter `requires_grad`/frozen concept. We therefore show
the `nnx.Param` count as the primary number and surface any other state
(BatchStat, RngState, ...) as a secondary "+N state" note.
"""

from __future__ import annotations

import html
import typing

from marimo._output.formatters._nn_tree import (
    _CSS,
    ModuleCategory,
    _comma_to_br,
    _fmt_integer,
    _footer_html,
)
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.hypertext import Html

if typing.TYPE_CHECKING:
    from flax import nnx  # type: ignore[import-not-found]

# Map flax.nnx.nn.<subpackage> to our display category. We derive the
# category from `type(module).__module__` without enumerating every class.
#
# This map is shorter than the PyTorch equivalent by design, not because
# layers are missing: NNX consolidates into a handful of subpackages what
# PyTorch splits across many (e.g. conv/sparse/linear all live in `linear`;
# every norm lives in `normalization`). It also keeps stateless ops
# (`relu`, pooling, padding, ...) as plain functions rather than modules,
# so they never appear in the tree. The keys below cover every
# `flax.nnx.nn.*` subpackage that contains Module classes; the structural
# containers (`Dict`, `List`, `Sequential`) are intentionally left
# uncategorized.
_MODULE_CATEGORY: dict[str, ModuleCategory] = {
    # Learnable / weighted layers
    "linear": "weight",  # Linear, LinearGeneral, Conv, ConvTranspose, Einsum, Embed
    "attention": "weight",  # MultiHeadAttention
    "recurrent": "weight",  # LSTMCell, GRUCell, RNN, Bidirectional, ...
    "lora": "weight",  # LoRA, LoRALinear
    # Parametric activations (most activations are functions, not modules)
    "activations": "act",  # PReLU
    # Normalization
    "normalization": "norm",  # BatchNorm, LayerNorm, RMSNorm, GroupNorm, InstanceNorm, ...
    # Regularization
    "stochastic": "reg",  # Dropout
}


def _layer_category(module: nnx.Module) -> ModuleCategory | None:
    """Classify a module for color-coding using its source subpackage."""
    mod_path = type(module).__module__ or ""
    if mod_path.startswith("flax.nnx.nn."):
        submod = mod_path.split("flax.nnx.nn.", 1)[1].split(".", 1)[0]
        return _MODULE_CATEGORY.get(submod)
    return None


def _child_modules(mod: nnx.Module) -> list[tuple[str, nnx.Module]]:
    """Direct submodules of `mod`, in definition order.

    NNX stores submodules as plain attributes, so we read them from the
    instance dict: this preserves the order they were assigned in
    `__init__` (matching PyTorch's `named_children`), whereas
    `nnx.iter_children` returns them sorted alphabetically by name. List
    and dict containers (e.g. `nnx.Sequential.layers`) are themselves
    modules whose items are stored under "0", "1", ... attributes, so the
    recursion handles them naturally.
    """
    from flax import nnx

    children: list[tuple[str, nnx.Module]] = []
    for name, value in vars(mod).items():
        if name.startswith("_"):
            continue
        if isinstance(value, nnx.Module):
            children.append((str(name), value))
    return children


def _param_leaves(mod: nnx.Module) -> list[typing.Any]:
    """Leaves (arrays) of the module's trainable `nnx.Param` state."""
    import jax  # type: ignore[import-not-found, unused-ignore]
    from flax import nnx

    try:
        return list(jax.tree.leaves(nnx.state(mod, nnx.Param)))
    except ValueError:
        # No matching state for the filter.
        return []


def _sum_size(leaves: typing.Iterable[typing.Any]) -> int:
    """Sum the number of elements across array leaves."""
    return sum(int(getattr(leaf, "size", 0)) for leaf in leaves)


def _counts(mod: nnx.Module) -> tuple[int, int, int]:
    """Return `(param_count, other_state_count, param_bytes)` for a subtree."""
    import jax  # type: ignore[import-not-found, unused-ignore]
    from flax import nnx

    param_leaves = _param_leaves(mod)
    param_count = _sum_size(param_leaves)
    param_bytes = sum(
        int(getattr(leaf, "size", 0)) * int(getattr(leaf, "itemsize", 0))
        for leaf in param_leaves
    )
    try:
        total = _sum_size(jax.tree.leaves(nnx.state(mod)))
    except ValueError:
        total = param_count
    return (param_count, max(total - param_count, 0), param_bytes)


def _collect_dtype_device(
    leaves: typing.Iterable[typing.Any],
) -> tuple[str, str]:
    """Summarise dtype and device across array leaves.

    Mirrors the PyTorch formatter: a single token when all leaves agree,
    unique values joined with `"/"` when mixed, and `"–"` when empty.
    """
    dtypes: set[str] = set()
    devices: set[str] = set()
    for leaf in leaves:
        dtype = getattr(leaf, "dtype", None)
        if dtype is not None:
            dtypes.add(str(dtype))
        try:
            for device in leaf.devices():
                devices.add(str(device))
        except (AttributeError, TypeError):
            pass
    if not dtypes:
        return ("–", "–")
    return (
        "/".join(sorted(dtypes)),
        "/".join(sorted(devices)) or "–",
    )


def _config_kwargs(mod: nnx.Module) -> str:
    """Build the HTML key=value config string from a module's attributes.

    NNX modules have no `extra_repr` hook, so we read the plain
    configuration attributes set in `__init__`. We keep only simple scalar
    values (skipping submodules, variables, callables, and `None`) to avoid
    noise, and highlight the keys like the PyTorch formatter does.
    """
    from flax import nnx

    parts: list[str] = []
    for key, value in vars(mod).items():
        if key.startswith("_"):
            continue
        if isinstance(value, (nnx.Module, nnx.Variable)):
            continue
        if not isinstance(value, (bool, int, float, str, tuple, list)):
            continue
        parts.append(
            f'<span class="nn-t-key">{html.escape(key)}</span>'
            f"={html.escape(repr(value))}"
        )
    return ", ".join(parts)


def _count_note(param_count: int, other_count: int) -> str:
    """Render the param/state count for a row's right-hand summary."""
    if param_count > 0:
        note = _fmt_integer(param_count)
        if other_count > 0:
            note += f" +{_fmt_integer(other_count)} state"
        return note
    if other_count > 0:
        return f"{_fmt_integer(other_count)} state"
    return ""


def _walk(name: str, mod: nnx.Module) -> str:
    """Recursively build HTML tree for an nnx.Module (non-root nodes)."""
    children = _child_modules(mod)
    type_name = mod.__class__.__name__
    cat = _layer_category(mod)

    name_html = f'<span class="nn-t-name">{html.escape(name)}</span> '
    cat_attr = f' data-cat="{cat}"' if cat is not None else ""
    type_span = f'<span class="nn-t-type"{cat_attr}>{type_name}</span>'

    if not children:
        param_count, other_count, _ = _counts(mod)
        kwargs = _config_kwargs(mod)
        note = _count_note(param_count, other_count)
        params = f'<span class="nn-t-params">{note}</span>' if note else ""

        # Build expand body: kwargs first, then dtype/device.
        body_parts: list[str] = []
        if kwargs:
            body_parts.append(_comma_to_br(kwargs))
        param_leaves = _param_leaves(mod)
        if param_leaves:
            dtype_s, device_s = _collect_dtype_device(param_leaves)
            if body_parts:
                body_parts.append(
                    '<div class="nn-t-expand-sep">'
                    '<span class="nn-t-expand-sep-label">array</span>'
                    "</div>"
                )
            body_parts.append(
                f'<span class="nn-t-key">dtype</span> {dtype_s}'
                f"<br>"
                f'<span class="nn-t-key">device</span> {device_s}'
            )

        if body_parts:
            kw_inline = (
                f' <span class="nn-t-args">{kwargs}</span>' if kwargs else ""
            )
            return (
                f'<details class="nn-t-expand">'
                f"<summary>"
                f'<span class="nn-t-spacer"></span>'
                f"{name_html}{type_span}{kw_inline}"
                f"{params}"
                f"</summary>"
                f'<div class="nn-t-expand-body">{"".join(body_parts)}</div>'
                f"</details>"
            )
        return (
            f'<div class="nn-t-leaf">'
            f'<span class="nn-t-spacer"></span>'
            f"{name_html}{type_span}"
            f"{params}"
            f"</div>"
        )

    # Container node: aggregate all descendant parameters and state.
    param_count, other_count, _ = _counts(mod)
    note = _count_note(param_count, other_count)
    total_params = f'<span class="nn-t-params">{note}</span>' if note else ""

    children_html = "\n".join(
        _walk(child_name, child_mod) for child_name, child_mod in children
    )

    return (
        f'<details class="nn-t-node">'
        f"<summary>"
        f'<span class="nn-t-arrow">&#9654;</span>'
        f"{name_html}{type_span}"
        f"{total_params}"
        f"</summary>"
        f'<div class="nn-t-children">{children_html}</div>'
        f"</details>"
    )


def format(module: nnx.Module) -> Html:  # noqa: A001
    """Render a Flax NNX module as a collapsible tree.

    The output shows the model name and summary in a fixed header,
    with child modules rendered as an expandable tree below.

    Args:
        module: A `flax.nnx.Module` instance.

    Returns:
        A `marimo.Html` object with the rendered tree.
    """
    children = _child_modules(module)
    total_params, total_other, total_bytes = _counts(module)
    size_mb = total_bytes / (1024 * 1024)

    state_note = f" +{_fmt_integer(total_other)} state" if total_other else ""
    header = (
        f'<div class="nn-t-header">'
        f'<span class="nn-t-root">{module.__class__.__name__}</span>'
        f'<span class="nn-t-summary">'
        f"{_fmt_integer(total_params)} params{state_note}"
        f" · {size_mb:.1f} MB"
        f"</span>"
        f"</div>"
    )

    if children:
        body_html = "\n".join(
            _walk(child_name, child_mod) for child_name, child_mod in children
        )
        body = f'<div class="nn-t-body">{body_html}</div>'
    else:
        kwargs = _config_kwargs(module)
        extra_html = (
            f'<span class="nn-t-args">{kwargs}</span>' if kwargs else ""
        )
        body = (
            f'<div class="nn-t-body">'
            f'<div class="nn-t-leaf">{extra_html}</div>'
            f"</div>"
        )

    divider = '<div class="nn-t-divider"></div>'
    footer = _footer_html()

    html_str = (
        f'<div class="nn-t"><style>{_CSS}</style>'
        f"{header}{divider}{body}{footer}"
        f"</div>"
    )
    return Html(html_str)


class FlaxFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "flax"

    def register(self) -> None:
        from flax import nnx  # type: ignore[import-not-found,unused-ignore]

        from marimo._messaging.mimetypes import KnownMimeType
        from marimo._output import formatting
        from marimo._output.formatters.flax_formatters import format as fmt

        @formatting.formatter(nnx.Module)
        def _format_module(
            module: nnx.Module,
        ) -> tuple[KnownMimeType, str]:
            return ("text/html", fmt(module).text)
