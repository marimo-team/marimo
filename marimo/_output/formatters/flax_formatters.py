# Copyright 2026 Marimo. All rights reserved.
"""Rich formatter for Flax NNX modules (`flax.nnx.Module`).

Renders an `nnx.Module` as the same collapsible tree as the PyTorch
formatter (shared presentation lives in `_nn_tree`). NNX is pythonically
close to PyTorch -- submodules are plain attributes -- but its parameter
model differs: variables are typed (`nnx.Param`, `nnx.BatchStat`, ...) and
there is no per-parameter `requires_grad`/frozen concept. We count only
trainable parameters (`nnx.Param`), mirroring the PyTorch formatter's
handling of parameters vs. buffers, so the two stay consistent.
"""

from __future__ import annotations

import html
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


def _counts(mod: nnx.Module) -> tuple[int, int]:
    """Return `(param_count, param_bytes)` for a subtree's trainable params.

    Like the PyTorch formatter, only trainable parameters (`nnx.Param`)
    are counted. Non-trainable state -- BatchNorm running statistics
    (`nnx.BatchStat`), PRNG keys (`nnx.RngState`), caches, etc. -- is left
    out, mirroring PyTorch's handling of buffers and keeping the two
    formatters consistent.
    """
    param_leaves = _param_leaves(mod)
    param_count = _sum_size(param_leaves)
    param_bytes = sum(
        int(getattr(leaf, "size", 0)) * int(getattr(leaf, "itemsize", 0))
        for leaf in param_leaves
    )
    return (param_count, param_bytes)


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


def _node(mod: nnx.Module, name: str = "") -> TreeNode:
    """Build a `TreeNode` for an nnx.Module (recursing into children)."""
    type_name = mod.__class__.__name__
    cat = _layer_category(mod)
    children = _child_modules(mod)

    if children:
        param_count, _ = _counts(mod)
        return TreeNode(
            name=name,
            type_name=type_name,
            category=cat,
            params_note=_fmt_integer(param_count) if param_count > 0 else "",
            children=[_node(c, n) for n, c in children],
        )

    # Leaf module: compute the Param leaves once and derive the count from
    # them, rather than calling `_counts` (which would walk the state again).
    param_leaves = _param_leaves(mod)
    param_count = _sum_size(param_leaves)
    kwargs = _config_kwargs(mod)
    body: LeafBody | None = None
    if kwargs or param_leaves:
        dtype = device = None
        if param_leaves:
            dtype, device = _collect_dtype_device(param_leaves)
        body = LeafBody(
            kwargs_inline=kwargs,
            kwargs_block=_comma_to_br(kwargs) if kwargs else "",
            dtype=dtype,
            device=device,
            array_label="array",
        )

    return TreeNode(
        name=name,
        type_name=type_name,
        category=cat,
        params_note=_fmt_integer(param_count) if param_count > 0 else "",
        # NNX has no frozen concept, but -- like PyTorch -- we dim
        # params-less leaves (e.g. Dropout) to match the legend.
        is_frozen=param_count == 0,
        body=body,
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
    total_params, total_bytes = _counts(module)
    size_mb = total_bytes / (1024 * 1024)
    summary = f"{_fmt_integer(total_params)} params · {size_mb:.1f} MB"

    leaf_fallback = "" if children else _config_kwargs(module)

    return render_model(
        root_type=module.__class__.__name__,
        summary=summary,
        nodes=[_node(c, n) for n, c in children],
        leaf_fallback=leaf_fallback,
    )


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
